"""LangGraph agent nodes for the Aegis workflow.

Each function is a node in the graph that operates on AgentState.
Together they form the Tier-2 Support Engineer pipeline:
  classify → write_sql → execute_sql → search_docs → propose_action → [HITL] → execute_action
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from langsmith import traceable

from app.agent.state import AgentState
from app.routing.model_router import get_model
from app.db.supabase import get_supabase
from app.observability.tracker import get_tracker


# ─────────────────────────────────────────────────────────────
# Node 1: Intent Classification
# ─────────────────────────────────────────────────────────────

@traceable(name="classify_intent")
async def classify_intent(state: AgentState) -> dict:
    """Classify the user's support ticket into a category.
    
    Uses the FAST/CHEAP model — this is simple classification.
    """
    llm = get_model("classify_intent")
    
    messages = [
        SystemMessage(content="""You are a support ticket classifier. Classify the user's message into exactly one category.

Categories:
- billing: Payment issues, refunds, charges, invoices, subscription costs
- technical: Bugs, errors, feature requests, API issues, performance problems
- account: Login issues, profile changes, plan upgrades/downgrades, account deletion
- general: Everything else

Respond with ONLY a JSON object: {"intent": "<category>", "confidence": <0.0-1.0>}"""),
        HumanMessage(content=state["user_message"]),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Track tokens
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics and hasattr(response, "usage_metadata") and response.usage_metadata:
        metrics.add_step(
            "classify_intent",
            llm.model_name if hasattr(llm, "model_name") else str(llm.model),
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )
    
    # Parse response
    try:
        result = json.loads(response.content.strip().strip("`").strip("json").strip())
        intent = result.get("intent", "general")
        confidence = result.get("confidence", 0.5)
    except (json.JSONDecodeError, AttributeError):
        intent = "general"
        confidence = 0.3
    
    return {
        "intent": intent,
        "intent_confidence": confidence,
        "thought_log": state.get("thought_log", []) + [
            f"✓ Classified intent: {intent} (confidence: {confidence:.0%})"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node 1.5: Customer Validation (comprehensive edge cases)
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
    from difflib import SequenceMatcher
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
        return f"⚠ Customer #{customer['id']} {customer['name']} is currently SUSPENDED"
    elif status == "cancelled":
        return f"⚠ Customer #{customer['id']} {customer['name']} account is CANCELLED"
    return None


@traceable(name="validate_customer")
async def validate_customer(state: AgentState) -> dict:
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
            "thought_log": thoughts + [
                "✓ No specific customer ID or name in message — proceeding with investigation"
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
                log_entries = [f"✓ Customer validated: #{customer['id']} {db_name} ({customer['plan']}, {customer['status']})"]
                if warning:
                    log_entries.append(warning)
                return {
                    "customer_found": True,
                    "thought_log": thoughts + log_entries,
                }
            
            # Check exact name match (case-insensitive)
            if mentioned_name.lower() == db_name.lower():
                # Case 1: ID + name match
                log_entries = [f"✓ Customer validated: #{customer['id']} {db_name} ({customer['plan']}, {customer['status']})"]
                if warning:
                    log_entries.append(warning)
                return {
                    "customer_found": True,
                    "thought_log": thoughts + log_entries,
                }
            
            # Check fuzzy match for typos
            similarity = _fuzzy_name_match(mentioned_name, db_name)
            if similarity >= _FUZZY_THRESHOLD:
                # Case 3: Typo — auto-correct with warning
                log_entries = [
                    f"⚠ Name typo detected: \"{mentioned_name}\" → auto-corrected to \"{db_name}\" (similarity: {similarity:.0%})",
                    f"✓ Customer validated: #{customer['id']} {db_name} ({customer['plan']}, {customer['status']})",
                ]
                if warning:
                    log_entries.append(warning)
                return {
                    "customer_found": True,
                    "thought_log": thoughts + log_entries,
                }
            
            # Case 2: ID exists but name clearly doesn't match
            return {
                "customer_found": False,
                "final_response": (
                    f"Customer ID #{customer_id} belongs to \"{db_name}\", "
                    f"but the ticket mentions \"{mentioned_name}\". "
                    f"Please verify the correct customer ID or name and try again."
                ),
                "thought_log": thoughts + [
                    f"✗ Name mismatch: ticket says \"{mentioned_name}\" but #{customer_id} is \"{db_name}\" — stopping"
                ],
            }
        
        else:
            # ID not found — fall through to name search if name is given
            if mentioned_name is None:
                # Case 8: ID not found, no name
                return {
                    "customer_found": False,
                    "final_response": f"Customer #{customer_id} was not found in our database. Please verify the customer ID and try again.",
                    "thought_log": thoughts + [
                        f"✗ Customer #{customer_id} not found in database — stopping"
                    ],
                }
            # Case 7: ID not found but name given → search by name below
            thoughts = thoughts + [
                f"⚠ Customer #{customer_id} not found — searching by name \"{mentioned_name}\" instead"
            ]
    
    # ── Cases 5, 7: Search by name ──
    if mentioned_name:
        matches = await _search_customers_by_name(db, mentioned_name)
        
        if len(matches) == 1:
            # Single match — use it
            customer = matches[0]
            warning = _status_warning(customer)
            log_entries = [
                f"✓ Customer found by name: #{customer['id']} {customer['name']} ({customer['plan']}, {customer['status']})",
            ]
            if customer_id is not None:
                log_entries.insert(0, f"⚠ Note: ticket said #{customer_id} but actual ID is #{customer['id']}")
            if warning:
                log_entries.append(warning)
            return {
                "customer_found": True,
                "thought_log": thoughts + log_entries,
            }
        
        elif len(matches) > 1:
            # Multiple matches — return candidates for disambiguation UI
            return {
                "customer_found": False,
                "customer_candidates": matches,
                "final_response": (
                    f"Multiple customers match \"{mentioned_name}\". "
                    f"Please select the correct customer to proceed."
                ),
                "thought_log": thoughts + [
                    f"✗ Ambiguous name \"{mentioned_name}\" — {len(matches)} matches found, need disambiguation"
                ],
            }
        
        else:
            # No matches at all — Case 8
            return {
                "customer_found": False,
                "final_response": (
                    f"No customer matching \"{mentioned_name}\" was found in our database. "
                    f"Please verify the customer information and try again."
                ),
                "thought_log": thoughts + [
                    f"✗ No customer found matching \"{mentioned_name}\" — stopping"
                ],
            }
    
    # Fallback — should not reach here
    return {
        "customer_found": True,
        "thought_log": thoughts + ["✓ Proceeding with investigation"],
    }


def should_proceed_after_validation(state: AgentState) -> str:
    """Conditional edge: only proceed if customer exists."""
    if state.get("customer_found", True):
        return "write_sql"
    return "generate_response"


# ─────────────────────────────────────────────────────────────
# Node 2: SQL Query Generation
# ─────────────────────────────────────────────────────────────

@traceable(name="write_sql")
async def write_sql(state: AgentState) -> dict:
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
        "thought_log": state.get("thought_log", []) + [
            "✓ Generated SQL query for investigation"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node 3: SQL Execution (with self-healing)
# ─────────────────────────────────────────────────────────────

@traceable(name="execute_sql")
async def execute_sql(state: AgentState) -> dict:
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
            "thought_log": state.get("thought_log", []) + [
                "✗ No SQL query to execute"
            ],
        }
    
    result = await db.execute_sql(sql)
    
    if result["success"]:
        records = result["data"] if isinstance(result["data"], list) else [result["data"]]
        return {
            "sql_result": records,
            "sql_error": "",
            "thought_log": state.get("thought_log", []) + [
                f"✓ SQL executed successfully — found {len(records)} records"
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
            "thought_log": state.get("thought_log", []) + [
                f"✗ SQL retry (attempt {retry_count + 1}/3): {display_error}"
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


# ─────────────────────────────────────────────────────────────
# Node 4: Documentation Search
# ─────────────────────────────────────────────────────────────

@traceable(name="search_docs")
async def search_docs(state: AgentState) -> dict:
    """Search internal documentation for relevant policies/procedures."""
    db = get_supabase()
    
    # Extract keywords from intent and message
    search_terms = state.get("intent", "general")
    docs = await db.search_docs(search_terms)
    
    if docs:
        docs_text = "\n\n".join(
            f"[{d['title']}] ({d['category']})\n{d['content'][:500]}"
            for d in docs
        )
        return {
            "docs_context": docs_text,
            "relevant_docs": [d["title"] for d in docs],
            "thought_log": state.get("thought_log", []) + [
                f"✓ Found {len(docs)} relevant internal documents"
            ],
        }
    
    return {
        "docs_context": "No internal documentation found for this topic.",
        "relevant_docs": [],
        "thought_log": state.get("thought_log", []) + [
            "✓ No specific internal docs found — using general knowledge"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node 5: Action Proposal (triggers HITL)
# ─────────────────────────────────────────────────────────────

@traceable(name="propose_action")
async def propose_action(state: AgentState) -> dict:
    """Synthesize all findings and propose an action.
    
    Uses the SMART model for critical reasoning.
    """
    llm = get_model("propose_action")
    
    sql_data = json.dumps(state.get("sql_result", []), indent=2, default=str)
    docs = state.get("docs_context", "None")
    
    # Check if we actually found a valid customer in the SQL results
    sql_results = state.get("sql_result", [])
    has_valid_customer = False
    if sql_results and isinstance(sql_results, list):
        for row in sql_results:
            if isinstance(row, dict) and row.get("id") and row.get("name"):
                has_valid_customer = True
                break
    
    customer_guard = ""
    if not has_valid_customer:
        customer_guard = """
CRITICAL: The SQL investigation found NO matching customer in the database. 
You MUST NOT propose refund, credit, or tier_change actions for non-existent customers.
Instead, use "escalate" with a description explaining the customer was not found, 
or use "resolve" if the ticket can be closed without action.
Set customer_id to null and customer_name to "Not Found"."""
    
    messages = [
        SystemMessage(content=f"""You are a senior support engineer deciding what action to take. Based on the investigation data, propose exactly ONE action.

Available action types:
- refund: Issue a monetary refund (specify amount)
- credit: Apply account credit (specify amount)
- tier_change: Change subscription tier (specify target tier)
- escalate: Escalate to human manager (for complex/sensitive cases)
- resolve: Mark as resolved with explanation (no action needed)
{customer_guard}
Respond with a JSON object:
{{
  "type": "<action_type>",
  "amount": <float or null>,
  "customer_id": <int or null>,
  "customer_name": "<string>",
  "description": "<what to do, 1 sentence>",
  "reason": "<why this is the right action, 1-2 sentences>"
}}"""),
        HumanMessage(content=f"""User message: {state['user_message']}
Intent: {state.get('intent', 'general')}

SQL Investigation Results:
{sql_data[:2000]}

Internal Documentation:
{docs[:1000]}

Propose the best action:"""),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Track tokens
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics and hasattr(response, "usage_metadata") and response.usage_metadata:
        metrics.add_step(
            "propose_action",
            llm.model_name if hasattr(llm, "model_name") else str(llm.model),
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )
    
    # Parse the proposed action
    try:
        action = json.loads(response.content.strip().strip("`").strip("json").strip())
    except (json.JSONDecodeError, AttributeError):
        action = {
            "type": "escalate",
            "amount": None,
            "customer_id": None,
            "customer_name": "Unknown",
            "description": "Unable to determine action — escalating to human manager",
            "reason": "The AI could not confidently parse a resolution.",
        }
    
    # ── Deterministic correction: override LLM-hallucinated customer info ──
    # Extract the real customer_id and customer_name from SQL results
    real_customer_id = None
    real_customer_name = None
    if sql_results and isinstance(sql_results, list):
        for row in sql_results:
            if isinstance(row, dict):
                # Look for customer ID — could be 'id' or 'customer_id'
                cid = row.get("id") or row.get("customer_id")
                cname = row.get("name") or row.get("customer_name")
                if cid and cname:
                    real_customer_id = cid
                    real_customer_name = cname
                    break
    
    if real_customer_id is not None:
        action["customer_id"] = real_customer_id
        action["customer_name"] = real_customer_name
    elif action.get("type") in ("refund", "credit", "tier_change"):
        # No real customer found but LLM proposed a financial action — force escalate
        action["type"] = "escalate"
        action["customer_id"] = None
        action["customer_name"] = "Not Found"
        action["description"] = f"Customer not found in database — escalating for manual review. Original proposal: {action.get('description', '')}"
        action["reason"] = "Cannot execute financial actions for unverified customers."
    
    return {
        "proposed_action": action,
        "thought_log": state.get("thought_log", []) + [
            f"✓ Proposed action: {action.get('type', 'unknown')} — {action.get('description', '')}"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node 6: HITL Interrupt — Wait for Human Approval
# ─────────────────────────────────────────────────────────────

@traceable(name="await_approval")
async def await_approval(state: AgentState) -> dict:
    """Pause the workflow and wait for human approval.
    
    This is the core HITL mechanism (Flex 1).
    The LangGraph interrupt() function literally pauses execution
    and waits for a resume command with the human's decision.
    """
    action = state.get("proposed_action", {})
    
    # Non-destructive actions can auto-approve
    if action.get("type") == "resolve":
        return {
            "approval_status": "approved",
            "thought_log": state.get("thought_log", []) + [
                "✓ Auto-approved: resolution requires no destructive action"
            ],
        }
    
    # For destructive actions, PAUSE and wait for human
    decision = interrupt({
        "type": "approval_required",
        "action": action,
        "message": f"AI proposes: {action.get('description', 'Unknown action')}",
        "requires_approval": True,
    })
    
    # This code runs AFTER human resumes the workflow
    if isinstance(decision, dict):
        approved = decision.get("approved", False)
        reason = decision.get("reason", "")
    else:
        approved = bool(decision)
        reason = ""
    
    status = "approved" if approved else "denied"
    
    return {
        "approval_status": status,
        "denial_reason": reason if not approved else "",
        "thought_log": state.get("thought_log", []) + [
            f"{'✓' if approved else '✗'} Human decision: {status}" + (f" — {reason}" if reason else "")
        ],
    }


def should_execute(state: AgentState) -> str:
    """Conditional edge: execute action if approved, generate response if denied."""
    if state.get("approval_status") == "approved":
        return "execute_action"
    return "generate_response"


# ─────────────────────────────────────────────────────────────
# Node 7: Action Execution (mock)
# ─────────────────────────────────────────────────────────────

@traceable(name="execute_action")
async def execute_action(state: AgentState) -> dict:
    """Execute the approved action (mock implementation).
    
    In production, this would call real APIs (Stripe, billing system, etc.)
    """
    action = state.get("proposed_action", {})
    action_type = action.get("type", "unknown")
    
    # Mock execution results
    mock_results = {
        "refund": f"Refund of ${(action.get('amount') or 0):.2f} processed successfully for customer {action.get('customer_name', 'Unknown')}. Transaction ID: TXN-{hash(str(action)) % 100000:05d}",
        "credit": f"Account credit of ${(action.get('amount') or 0):.2f} applied to customer {action.get('customer_name', 'Unknown')}'s account.",
        "tier_change": f"Subscription tier changed for customer {action.get('customer_name', 'Unknown')}. Changes take effect immediately.",
        "escalate": f"Ticket escalated to senior support manager. Reference: ESC-{hash(str(action)) % 10000:04d}",
        "resolve": "Ticket resolved. No further action required.",
    }
    
    result = mock_results.get(action_type, "Action completed.")
    
    # Track in observability
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics:
        metrics.approved = True
    
    return {
        "execution_result": result,
        "thought_log": state.get("thought_log", []) + [
            f"✓ Action executed: {result}"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node 8: Final Response Generation
# ─────────────────────────────────────────────────────────────

@traceable(name="generate_response")
async def generate_response(state: AgentState) -> dict:
    """Generate a final human-readable summary response."""
    
    # If validate_customer already set a final_response (not found, mismatch, etc.),
    # preserve it — don't let the LLM overwrite it with hallucinated content.
    if state.get("final_response") and state.get("customer_found") is False:
        return {
            "thought_log": state.get("thought_log", []) + [
                "✓ Response already set by validation — skipping LLM generation"
            ],
        }
    
    # If SQL returned 0 records, generate a clear "not found" response without LLM
    sql_result = state.get("sql_result", [])
    if not state.get("sql_error") and len(sql_result) == 0 and state.get("customer_found") is True:
        return {
            "final_response": f"No matching billing or transaction records were found for Customer #{state.get('user_message', '')}. "
                              f"The database query returned 0 results. This could mean the reported issue doesn't have a matching record, "
                              f"or the details provided may need clarification.",
            "thought_log": state.get("thought_log", []) + [
                "⚠ No records found in database — no action required"
            ],
        }
    
    llm = get_model("generate_response")
    
    action = state.get("proposed_action", {})
    approved = state.get("approval_status") == "approved"
    execution = state.get("execution_result", "")
    denied_reason = state.get("denial_reason", "")
    
    messages = [
        SystemMessage(content="You are a support engineer writing a brief resolution summary. Be professional and concise. 2-3 sentences max."),
        HumanMessage(content=f"""Original issue: {state['user_message']}
Intent: {state.get('intent', 'general')}
Proposed action: {action.get('description', 'None')}
Action status: {'Approved and executed' if approved else f'Denied by manager — {denied_reason}' if denied_reason else 'Denied by manager'}
Execution result: {execution if approved else 'N/A'}

Write a brief resolution summary:"""),
    ]
    
    response = await llm.ainvoke(messages)
    
    # Track tokens
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics and hasattr(response, "usage_metadata") and response.usage_metadata:
        metrics.add_step(
            "generate_response",
            llm.model_name if hasattr(llm, "model_name") else str(llm.model),
            response.usage_metadata.get("input_tokens", 0),
            response.usage_metadata.get("output_tokens", 0),
        )
    
    return {
        "final_response": response.content,
        "thought_log": state.get("thought_log", []) + [
            "✓ Generated resolution summary"
        ],
    }
