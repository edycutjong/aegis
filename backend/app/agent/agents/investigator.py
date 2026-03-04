"""Investigator Agent — Customer Validation & SQL Investigation.

The Investigator Agent is the data specialist of the Aegis workflow.
It validates customer identity (handling 8 edge cases including fuzzy name
matching), generates SQL queries to investigate issues, executes them against
Supabase, and implements a self-healing retry loop for failed queries.

This agent produces the raw evidence that downstream agents use for decisions.
"""

from difflib import SequenceMatcher

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.agent.state import AgentState
from app.routing.model_router import get_model
from app.db.supabase import get_supabase
from app.observability.tracker import get_tracker


AGENT_NAME = "Investigator"
AGENT_DESCRIPTION = (
    "Validates customer identity, generates and executes SQL queries to "
    "investigate support issues, with self-healing retry on failures."
)


# ─────────────────────────────────────────────────────────────
# Customer Validation Helpers
# ─────────────────────────────────────────────────────────────

def _extract_customer_info(message: str) -> tuple[int | None, str | None]:
    """Extract customer ID and name from a support ticket message.
    
    Returns (customer_id, mentioned_name) — either can be None.
    """
    import re
    
    # Extract ID: "Customer #8", "customer 8", "Customer#8"
    id_match = re.search(r'[Cc]ustomer\s*#?(\d+)', message)
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
    
    return customer_id, mentioned_name


def _fuzzy_name_match(name_a: str, name_b: str) -> float:
    """Return similarity ratio (0.0–1.0) between two names."""
    return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()


_FUZZY_THRESHOLD = 0.75  # "Davd Martinez" vs "David Martinez" ≈ 0.93


async def _search_customers_by_name(db, name: str) -> list[dict]:
    """Search customers by name (case-insensitive partial match)."""
    # Split into parts for better matching
    parts = name.strip().split()
    if len(parts) >= 2:
        # Search by first AND last name
        query = (
            f"SELECT id, name, email, plan, status FROM customers "
            f"WHERE LOWER(name) LIKE '%{parts[0].lower()}%' "
            f"AND LOWER(name) LIKE '%{parts[-1].lower()}%' "
            f"LIMIT 5"
        )
    else:
        query = (
            f"SELECT id, name, email, plan, status FROM customers "
            f"WHERE LOWER(name) LIKE '%{name.lower()}%' "
            f"LIMIT 5"
        )
    result = await db.execute_sql(query)
    if result["success"] and result.get("data"):
        return result["data"]
    return []


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
async def validate_customer(state: AgentState, config: dict | None = None) -> dict:
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
    thoughts = state.get("thought_log", [])
    
    # ── Case 6: No ID and no name → let SQL figure it out ──
    if customer_id is None and mentioned_name is None:
        return {
            "customer_found": True,
            "active_agent": AGENT_NAME,
            "thought_log": thoughts + [
                f"✓ [{AGENT_NAME}] No specific customer ID or name in message — proceeding with investigation"
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
    """Conditional edge: only proceed if customer exists."""
    if state.get("customer_found", True):
        return "write_sql"
    return "generate_response"


# ─────────────────────────────────────────────────────────────
# Node: SQL Query Generation
# ─────────────────────────────────────────────────────────────

@traceable(name="write_sql")
async def write_sql(state: AgentState, config: dict | None = None) -> dict:
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
        HumanMessage(content=f"User message: {state['user_message']}\nClassified intent: {state.get('intent', 'general')}"),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Track tokens
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics and hasattr(response, "usage_metadata") and response.usage_metadata:
        metrics.add_step(
            "write_sql",
            llm.model_name if hasattr(llm, "model_name") else str(llm.model),
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )
    
    sql = response.content.strip().strip("`").strip("sql").strip()
    
    return {
        "sql_query": sql,
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"✓ [{AGENT_NAME}] Generated SQL query for investigation"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node: SQL Execution (with self-healing)
# ─────────────────────────────────────────────────────────────

@traceable(name="execute_sql")
async def execute_sql(state: AgentState, config: dict | None = None) -> dict:
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
    
    result = await db.execute_sql(sql)
    
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
