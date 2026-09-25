"""Investigator Agent — Customer Validation & SQL Investigation.

The Investigator Agent is the data specialist of the Aegis workflow.
It validates customer identity (handling 8 edge cases including fuzzy name
matching), generates SQL queries to investigate issues, executes them against
Supabase, and implements a self-healing retry loop for failed queries.

This agent produces the raw evidence that downstream agents use for decisions.
"""

import re
from difflib import SequenceMatcher

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from app.agent.state import AgentState
from app.routing.model_router import failover_note, get_model, resolved_model_name
from app.db.supabase import get_supabase
from app.db.sql_guard import check_sql
from app.observability.tracker import get_tracker


AGENT_NAME = "Investigator"


# ─────────────────────────────────────────────────────────────
# Customer Validation Helpers
# ─────────────────────────────────────────────────────────────

# Opening words that are capitalized because they start a sentence, not names.
_NOT_A_FIRST_NAME = frozenset(
    "please hi hello hey dear urgent the our my your we i can could would why how what when "
    "where who is are do does need help thanks thank refund billing account customer".split()
)


_CUSTOMER_ID = re.compile(
    r"\b(?:customer|cust|acct|account|client)\b\.?\s*(?:no\.?|number|id)?\s*[:#]?\s*(\d{1,6})\b",
    re.IGNORECASE,
)
_BARE_ID = re.compile(
    r"(?<![\w#])(?<!ticket )(?<!invoice )(?<!order )(?<!case )(?<!ref )#(\d{1,6})\b",
    re.IGNORECASE,
)
_ROSTER_MATCH_THRESHOLD = 0.85  # a typo'd full name ("Jenifer Tayler"), not two random words


def _customers_named_in_text(message: str, roster: list[dict]) -> list[str]:
    """Every roster customer named exactly (full name or email), in text order."""
    text = message.lower()
    found = []
    for customer in roster:
        name = (customer.get("name") or "").lower()
        email = (customer.get("email") or "").lower()
        hits = [m.start() for m in [re.search(rf"\b{re.escape(name)}\b", text)] if name and m]
        if email and email in text:
            hits.append(text.index(email))
        if hits:
            found.append((min(hits), customer["name"]))
    return [name for _, name in sorted(found)]


def _find_customer_in_text(message: str, roster: list[dict]) -> str | None:
    """The roster customer a ticket names, however it is written.

    Matches an email address first, then a full name anywhere in the text
    (any case, any position), then a company name, then a close typo of a
    full name. Returns the customer's name as stored, or None.
    """
    text = message.lower()
    for customer in roster:
        email = (customer.get("email") or "").lower()
        if email and email in text:
            return customer["name"]

    found = []
    for customer in roster:
        name = (customer.get("name") or "").lower()
        hit = re.search(rf"\b{re.escape(name)}\b", text) if name else None
        if hit:
            found.append((hit.start(), customer["name"]))
    if found:
        return min(found)[1]  # the first one the ticket mentions

    # A company name ("kevin from gamedev studio", "InnovaTech Labs accounts
    # team", "rob kim @ cloudpeak"). Matched on letters and digits only, so
    # "E-Com Shop" and "ecomshop" agree; the first word alone counts when it
    # is distinctive. Companies are unique per customer in this dataset.
    compact_text = re.sub(r"[^a-z0-9]", "", text)
    for customer in roster:
        company = (customer.get("company") or "").lower()
        compact = re.sub(r"[^a-z0-9]", "", company)
        first = company.split()[0] if company.split() else ""
        if (len(compact) >= 6 and compact in compact_text) or (
            len(first) >= 6 and re.search(rf"\b{re.escape(first)}\b", text)
        ):
            return customer["name"]

    words = re.findall(r"[a-z]+(?:['-][a-z]+)*", text)
    best, best_name = 0.0, None
    for first, last in zip(words, words[1:]):
        window = f"{first} {last}"
        for customer in roster:
            ratio = _fuzzy_name_match(window, customer.get("name") or "")
            if ratio > best:
                best, best_name = ratio, customer["name"]
    return best_name if best >= _ROSTER_MATCH_THRESHOLD else None


def _close_to_a_customer(name: str, roster: list[dict]) -> bool:
    return any(_fuzzy_name_match(name, c.get("name") or "") >= _FUZZY_THRESHOLD for c in roster)


def _extract_customer_info(message: str) -> tuple[int | None, str | None]:
    """Extract customer ID and name from a support ticket message.

    Returns (customer_id, mentioned_name) — either can be None.
    """
    import re

    # Extract ID: "Customer #8", "customer 8", "acct 10", "account #3",
    # "customer no. 4", "(#8)", "#17". A bare "#N" counts unless it names
    # something else ("ticket #123", "invoice #9").
    id_match = _CUSTOMER_ID.search(message) or _BARE_ID.search(message)
    customer_id = int(id_match.group(1)) if id_match else None

    # Extract name after customer ID: "Customer #8 David Martinez"
    mentioned_name = None
    if id_match:
        name_match = re.search(
            r'[Cc]ustomer\s*#?\d+[\s,]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', message
        )
        if name_match:
            mentioned_name = name_match.group(1).strip()
    else:
        # No ID — try to extract a standalone name
        # Look for common patterns: "Customer David Martinez", "for David Martinez"
        name_match = re.search(
            r'(?:[Cc]ustomer|[Ff]or|[Cc]lient)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', message
        )
        if name_match:
            mentioned_name = name_match.group(1).strip()
        else:
            # A ticket that opens with the name: "Emily Davis reports her ..."
            lead = re.match(r"\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)(?:\s+[a-z]|'s\b)", message)
            if lead and lead.group(1).lower() not in _NOT_A_FIRST_NAME:
                mentioned_name = f"{lead.group(1)} {lead.group(2)}"

    return customer_id, mentioned_name


def _strip_fences(text: str) -> str:
    """Remove markdown code fences the model sometimes wraps SQL in.

    The previous `.strip("sql")` stripped a *character set*, not a prefix, so
    a query ending in "...ORDER BY email" silently lost its final "l".
    """
    import re

    text = text.strip()
    fenced = re.search(r"```(?:sql|postgresql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    return text.strip().rstrip(";").strip()


def _name_is_explicit(message: str, name: str) -> bool:
    """True when the name was introduced as a customer ("for X", "Customer X")."""
    import re

    return bool(re.search(rf"(?:[Cc]ustomer|[Ff]or|[Cc]lient)\s+{re.escape(name)}", message))


def _fuzzy_name_match(name_a: str, name_b: str) -> float:
    """Return similarity ratio (0.0–1.0) between two names."""
    return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()


_FUZZY_THRESHOLD = 0.75  # "Davd Martinez" vs "David Martinez" ≈ 0.93


async def _search_customers_by_name(db, name: str) -> list[dict]:
    """Search customers by name (case-insensitive; every name part must match)."""
    parts = name.strip().split()
    return await db.search_customers([parts[0], parts[-1]] if len(parts) >= 2 else parts)


def _status_warning(customer: dict) -> str | None:
    """Return a warning string if customer is not active."""
    status = customer.get("status", "active")
    if status == "suspended":
        return f"⚠ [{AGENT_NAME}] Customer #{customer['id']} {customer['name']} is currently SUSPENDED"
    elif status == "cancelled":
        return f"⚠ [{AGENT_NAME}] Customer #{customer['id']} {customer['name']} account is CANCELLED"
    return None


# ─────────────────────────────────────────────────────────────
# Node: Customer Validation
# ─────────────────────────────────────────────────────────────

@traceable(name="validate_customer")
async def validate_customer(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Validate the customer, then gather their billing records as evidence.

    The billing rows are fetched here, deterministically, because they bound
    every refund and credit downstream; the model's own SQL chooses its column
    names and can't be relied on to expose `type` or `amount`.
    """
    db = get_supabase()
    roster = await db.list_customers()
    result = await _validate_identity(state, roster)
    customer = result.get("customer")
    if customer and customer.get("id") is not None:
        result["billing"] = await db.get_billing(customer["id"])
        others = [n for n in _customers_named_in_text(state["user_message"], roster) if n != customer.get("name")]
        if others:
            result["other_customers"] = others
    return result


async def _validate_identity(state: AgentState, roster: list[dict]) -> dict:
    """Validate customer identity before investigation.

    Handles 8 edge cases:
    1. ID + name match         → proceed (warn if suspended/cancelled)
    2. ID + name mismatch      → stop
    3. ID + name typo (fuzzy)  → proceed with auto-correct warning
    4. ID only, no name        → proceed
    5. No ID + name given      → search by name, disambiguate
    6. No ID + no name         → proceed (let SQL figure it out)
    7. ID not found + name     → search by name as fallback
    8. Both not found          → stop
    """
    user_msg = state["user_message"]
    customer_id, mentioned_name = _extract_customer_info(user_msg)
    db = get_supabase()

    # The regex only sees "Customer #N First Last". The roster finds names
    # written any other way ("chris johnson, acct 10", "Robert Kim here",
    # an email address, a typo). With an ID, a regex name close to a real
    # customer is kept, so the typo and mismatch checks against that ID's row
    # still see what was written. Without an ID, the roster's spelling is
    # used: the name search below is exact, so "Jenifer Tayler" found no one.
    thoughts = state.get("thought_log", [])
    roster_name = _find_customer_in_text(user_msg, roster)
    if roster_name and (
        mentioned_name is None or customer_id is None or not _close_to_a_customer(mentioned_name, roster)
    ):
        if mentioned_name and mentioned_name != roster_name:
            thoughts = thoughts + [f"⚠ [{AGENT_NAME}] \"{mentioned_name}\" read as customer \"{roster_name}\""]
        mentioned_name = roster_name

    # ── Case 6: No ID and no name → let SQL figure it out ──
    if customer_id is None and mentioned_name is None:
        return {
            "customer_found": True,
            "active_agent": AGENT_NAME,
            "thought_log": thoughts + [
                f"✓ [{AGENT_NAME}] No customer identified — skipping account lookups, answering from policy docs only"
            ],
        }

    # ── Cases 1-4: ID provided → look up by ID ──
    if customer_id is not None:
        result = await db.execute_sql(
            f"SELECT id, name, email, plan, status FROM customers WHERE id = {customer_id} LIMIT 1"
        )
        id_found = result["success"] and result.get("data") and len(result["data"]) > 0

        if id_found:
            customer = result["data"][0]
            db_name = customer["name"]
            warning = _status_warning(customer)

            if mentioned_name is None:
                # Case 4: ID only, no name
                log_entries = [f"✓ [{AGENT_NAME}] Customer validated: #{customer['id']} {db_name} ({customer['plan']}, {customer['status']})"]
                if warning:
                    log_entries.append(warning)
                return {
                    "customer_found": True,
                    "customer": customer,
                    "active_agent": AGENT_NAME,
                    "thought_log": thoughts + log_entries,
                }

            # Check exact name match (case-insensitive)
            if mentioned_name.lower() == db_name.lower():
                # Case 1: ID + name match
                log_entries = [f"✓ [{AGENT_NAME}] Customer validated: #{customer['id']} {db_name} ({customer['plan']}, {customer['status']})"]
                if warning:
                    log_entries.append(warning)
                return {
                    "customer_found": True,
                    "customer": customer,
                    "active_agent": AGENT_NAME,
                    "thought_log": thoughts + log_entries,
                }

            # Check fuzzy match for typos
            similarity = _fuzzy_name_match(mentioned_name, db_name)
            if similarity >= _FUZZY_THRESHOLD:
                # Case 3: Typo — auto-correct with warning
                log_entries = [
                    f"⚠ [{AGENT_NAME}] Name typo detected: \"{mentioned_name}\" → auto-corrected to \"{db_name}\" (similarity: {similarity:.0%})",
                    f"✓ [{AGENT_NAME}] Customer validated: #{customer['id']} {db_name} ({customer['plan']}, {customer['status']})",
                ]
                if warning:
                    log_entries.append(warning)
                return {
                    "customer_found": True,
                    "customer": customer,
                    "active_agent": AGENT_NAME,
                    "thought_log": thoughts + log_entries,
                }

            # Case 2: ID exists but name clearly doesn't match
            return {
                "customer_found": False,
                "active_agent": AGENT_NAME,
                "final_response": (
                    f"Customer ID #{customer_id} belongs to \"{db_name}\", "
                    f"but the ticket mentions \"{mentioned_name}\". "
                    f"Please verify the correct customer ID or name and try again."
                ),
                "thought_log": thoughts + [
                    f"✗ [{AGENT_NAME}] Name mismatch: ticket says \"{mentioned_name}\" but #{customer_id} is \"{db_name}\" — stopping"
                ],
            }

        else:
            # ID not found — fall through to name search if name is given
            if mentioned_name is None:
                # Case 8: ID not found, no name
                return {
                    "customer_found": False,
                    "active_agent": AGENT_NAME,
                    "final_response": f"Customer #{customer_id} was not found in our database. Please verify the customer ID and try again.",
                    "thought_log": thoughts + [
                        f"✗ [{AGENT_NAME}] Customer #{customer_id} not found in database — stopping"
                    ],
                }
            # Case 7: ID not found but name given → search by name below
            thoughts = thoughts + [
                f"⚠ [{AGENT_NAME}] Customer #{customer_id} not found — searching by name \"{mentioned_name}\" instead"
            ]

    # ── Cases 5, 7: Search by name ──
    if mentioned_name:
        matches = await _search_customers_by_name(db, mentioned_name)

        if len(matches) == 1:
            # Single match — use it
            customer = matches[0]
            warning = _status_warning(customer)
            log_entries = [
                f"✓ [{AGENT_NAME}] Customer found by name: #{customer['id']} {customer['name']} ({customer['plan']}, {customer['status']})",
            ]
            if customer_id is not None:
                log_entries.insert(0, f"⚠ [{AGENT_NAME}] Note: ticket said #{customer_id} but actual ID is #{customer['id']}")
            if warning:
                log_entries.append(warning)
            return {
                "customer_found": True,
                "customer": customer,
                "active_agent": AGENT_NAME,
                "thought_log": thoughts + log_entries,
            }

        elif len(matches) > 1:
            # Multiple matches — return candidates for disambiguation UI
            return {
                "customer_found": False,
                "customer_candidates": matches,
                "active_agent": AGENT_NAME,
                "final_response": (
                    f"Multiple customers match \"{mentioned_name}\". "
                    f"Please select the correct customer to proceed."
                ),
                "thought_log": thoughts + [
                    f"✗ [{AGENT_NAME}] Ambiguous name \"{mentioned_name}\" — {len(matches)} matches found, need disambiguation"
                ],
            }

        elif customer_id is None and not _name_is_explicit(user_msg, mentioned_name):
            # A guessed leading name ("Dark Mode is broken") that matches no
            # one is not a customer reference — treat it as case 6.
            return {
                "customer_found": True,
                "active_agent": AGENT_NAME,
                "thought_log": thoughts + [
                    f"✓ [{AGENT_NAME}] No customer identified — skipping account lookups, answering from policy docs only"
                ],
            }

        else:
            # No matches at all — Case 8
            return {
                "customer_found": False,
                "active_agent": AGENT_NAME,
                "final_response": (
                    f"No customer matching \"{mentioned_name}\" was found in our database. "
                    f"Please verify the customer information and try again."
                ),
                "thought_log": thoughts + [
                    f"✗ [{AGENT_NAME}] No customer found matching \"{mentioned_name}\" — stopping"
                ],
            }

    # Fallback — should not reach here
    return {  # pragma: no cover
        "customer_found": True,
        "active_agent": AGENT_NAME,
        "thought_log": thoughts + [f"✓ [{AGENT_NAME}] Proceeding with investigation"],
    }


def should_proceed_after_validation(state: AgentState) -> str:
    """Conditional edge after validation.

    Model-written SQL only runs for a validated customer. With no customer
    identified, the ticket is answered from policy docs alone: an open query
    across every customer is how an unverified "auditor" got totals of all
    customers and revenue into an auto-resolve.
    """
    if not state.get("customer_found", True):
        return "generate_response"
    if (state.get("customer") or {}).get("id") is None:
        return "search_docs"
    return "write_sql"


def _validated_customer_hint(state: AgentState) -> str:
    """Tell the SQL writer who the customer actually is.

    Validation may have corrected the ticket (wrong ID, typo'd name); without
    this the model trusts the ticket text and queries the wrong customer_id.
    """
    customer = state.get("customer") or {}
    if not customer.get("id"):
        return ""
    return (
        f"\nValidated customer: id={customer['id']}, name={customer.get('name')!r}. "
        f"Use customer_id = {customer['id']} — it overrides any ID written in the ticket."
    )


# ─────────────────────────────────────────────────────────────
# Node: SQL Query Generation
# ─────────────────────────────────────────────────────────────

@traceable(name="write_sql")
async def write_sql(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Generate a SQL query to investigate the user's issue.

    Uses the SMART/EXPENSIVE model — SQL generation is complex.
    """
    llm = get_model("write_sql")

    error_context = ""
    if state.get("sql_error"):
        error_context = f"""
Your previous SQL query failed with this error:
Query: {state.get('sql_query', '')}
Error: {state['sql_error']}

Fix the query and try again. Do NOT repeat the same mistake."""

    messages = [
        SystemMessage(content=f"""You are a database engineer. Write a PostgreSQL query to investigate the user's support issue.

Available tables and their schemas:
- customers (id SERIAL PK, name TEXT, email TEXT, plan TEXT ['free','pro','enterprise'], status TEXT ['active','suspended','cancelled'], created_at TIMESTAMPTZ)
- billing (id SERIAL PK, customer_id INT FK→customers, amount DECIMAL, type TEXT ['charge','refund','credit'], description TEXT, created_at TIMESTAMPTZ)
- support_tickets (id SERIAL PK, customer_id INT FK→customers, subject TEXT, body TEXT, priority TEXT ['low','medium','high','critical'], status TEXT ['open','in_progress','resolved','escalated'], category TEXT, created_at TIMESTAMPTZ)
- internal_docs (id SERIAL PK, title TEXT, content TEXT, category TEXT)

Rules:
- Write SELECT queries ONLY. Never INSERT, UPDATE, DELETE, or DROP.
- Always LIMIT results to 20 rows max.
- Use JOINs to get full context when investigating a user.
- If a customer ID is mentioned, query their full profile + billing + tickets.
{error_context}

Respond with ONLY the SQL query, no explanation, no markdown fences."""),
        HumanMessage(content=(
            f"User message: {state['user_message']}\n"
            f"Classified intent: {state.get('intent', 'general')}"
            + _validated_customer_hint(state)
        )),
    ]

    response = await llm.ainvoke(messages)

    # Track tokens
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics and hasattr(response, "usage_metadata") and response.usage_metadata:
        metrics.add_step(
            "write_sql",
            resolved_model_name(llm, response),
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )

    sql = _strip_fences(response.content or "")

    return {
        "sql_query": sql,
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + failover_note("write_sql", AGENT_NAME, llm, response) + [
            f"✓ [{AGENT_NAME}] Generated SQL query for investigation"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node: SQL Execution (with self-healing)
# ─────────────────────────────────────────────────────────────

@traceable(name="execute_sql")
async def execute_sql(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """Execute the generated SQL against Supabase.

    If it fails, records the error for the self-healing retry loop.
    """
    db = get_supabase()
    sql = state.get("sql_query", "")
    retry_count = state.get("sql_retry_count", 0)

    if not sql:
        return {
            "sql_result": [],
            "sql_error": "No SQL query generated",
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"✗ [{AGENT_NAME}] No SQL query to execute"
            ],
        }

    # Guard first: a rejection is fed back to write_sql as the error, so the
    # self-healing loop can repair the query instead of the DB ever seeing it.
    guard = check_sql(sql)
    if not guard.ok:
        return {
            "sql_result": [],
            "sql_error": f"Blocked by SQL guard: {guard.reason}",
            "sql_retry_count": retry_count + 1,
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"🛡 [{AGENT_NAME}] SQL guard blocked query (attempt {retry_count + 1}/3): {guard.reason}"
            ],
        }

    result = await db.execute_sql(guard.sql)

    if result["success"]:
        records = result["data"] if isinstance(result["data"], list) else [result["data"]]
        return {
            "sql_result": records,
            "sql_error": "",
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"✓ [{AGENT_NAME}] SQL executed successfully — found {len(records)} records"
            ],
        }
    else:
        # Parse error for clean UI display
        raw_error = result.get("error", "Unknown database error")
        if isinstance(raw_error, dict):
            display_error = raw_error.get("message", str(raw_error))
        elif isinstance(raw_error, str):
            # Try to extract "message" from JSON-like strings
            try:
                import json
                parsed = json.loads(raw_error)
                display_error = parsed.get("message", raw_error)
            except (json.JSONDecodeError, AttributeError):
                display_error = raw_error[:100]
        else:
            display_error = str(raw_error)[:100]

        return {
            "sql_result": [],
            "sql_error": raw_error,  # Keep full error for debugging
            "sql_retry_count": retry_count + 1,
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"✗ [{AGENT_NAME}] SQL retry (attempt {retry_count + 1}/3): {display_error}"
            ],
        }


def should_retry_sql(state: AgentState) -> str:
    """Conditional edge: retry SQL, short-circuit on 0 records, or proceed."""
    if state.get("sql_error") and state.get("sql_retry_count", 0) < 3:
        return "write_sql"  # Self-healing loop

    # If SQL succeeded but returned 0 records, short-circuit
    records = state.get("sql_result", [])
    if not state.get("sql_error") and len(records) == 0:
        return "generate_response"  # No data found

    return "search_docs"
