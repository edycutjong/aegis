"""LangGraph agent nodes for the Aegis workflow.

Each function is a node in the graph that operates on AgentState.
Together they form the Tier-2 Support Engineer pipeline:
  classify → write_sql → execute_sql → search_docs → propose_action → [HITL] → execute_action
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from app.agent.state import AgentState
from app.routing.model_router import get_model
from app.db.supabase import get_supabase
from app.observability.tracker import get_tracker


# ─────────────────────────────────────────────────────────────
# Node 1: Intent Classification
# ─────────────────────────────────────────────────────────────

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
# Node 2: SQL Query Generation
# ─────────────────────────────────────────────────────────────

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
        return {
            "sql_result": result["data"] if isinstance(result["data"], list) else [result["data"]],
            "sql_error": "",
            "thought_log": state.get("thought_log", []) + [
                f"✓ SQL executed successfully — found {len(result.get('data', []))} records"
            ],
        }
    else:
        return {
            "sql_result": [],
            "sql_error": result.get("error", "Unknown database error"),
            "sql_retry_count": retry_count + 1,
            "thought_log": state.get("thought_log", []) + [
                f"✗ SQL error (attempt {retry_count + 1}/3): {result.get('error', 'Unknown')[:100]}"
            ],
        }


def should_retry_sql(state: AgentState) -> str:
    """Conditional edge: retry SQL or proceed to docs search."""
    if state.get("sql_error") and state.get("sql_retry_count", 0) < 3:
        return "write_sql"  # Self-healing loop
    return "search_docs"


# ─────────────────────────────────────────────────────────────
# Node 4: Documentation Search
# ─────────────────────────────────────────────────────────────

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

async def propose_action(state: AgentState) -> dict:
    """Synthesize all findings and propose an action.
    
    Uses the SMART model for critical reasoning.
    """
    llm = get_model("propose_action")
    
    sql_data = json.dumps(state.get("sql_result", []), indent=2, default=str)
    docs = state.get("docs_context", "None")
    
    messages = [
        SystemMessage(content="""You are a senior support engineer deciding what action to take. Based on the investigation data, propose exactly ONE action.

Available action types:
- refund: Issue a monetary refund (specify amount)
- credit: Apply account credit (specify amount)
- tier_change: Change subscription tier (specify target tier)
- escalate: Escalate to human manager (for complex/sensitive cases)
- resolve: Mark as resolved with explanation (no action needed)

Respond with a JSON object:
{
  "type": "<action_type>",
  "amount": <float or null>,
  "customer_id": <int or null>,
  "customer_name": "<string>",
  "description": "<what to do, 1 sentence>",
  "reason": "<why this is the right action, 1-2 sentences>"
}"""),
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
    
    return {
        "proposed_action": action,
        "thought_log": state.get("thought_log", []) + [
            f"✓ Proposed action: {action.get('type', 'unknown')} — {action.get('description', '')}"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node 6: HITL Interrupt — Wait for Human Approval
# ─────────────────────────────────────────────────────────────

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

async def execute_action(state: AgentState) -> dict:
    """Execute the approved action (mock implementation).
    
    In production, this would call real APIs (Stripe, billing system, etc.)
    """
    action = state.get("proposed_action", {})
    action_type = action.get("type", "unknown")
    
    # Mock execution results
    mock_results = {
        "refund": f"Refund of ${action.get('amount', 0):.2f} processed successfully for customer {action.get('customer_name', 'Unknown')}. Transaction ID: TXN-{hash(str(action)) % 100000:05d}",
        "credit": f"Account credit of ${action.get('amount', 0):.2f} applied to customer {action.get('customer_name', 'Unknown')}'s account.",
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

async def generate_response(state: AgentState) -> dict:
    """Generate a final human-readable summary response."""
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
