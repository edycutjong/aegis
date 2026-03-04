"""Resolution Agent — Action Proposal, Approval & Execution.

The Resolution Agent is the decision-maker of the Aegis workflow.
It synthesizes investigation data and documentation into a concrete action
proposal (refund, credit, tier change, escalate, resolve), manages the
Human-in-the-Loop approval gate, executes approved actions, and generates
the final response summary.

This agent handles the most critical part of the workflow — the actions
that affect real customer accounts.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt
from langsmith import traceable

from app.agent.state import AgentState
from app.routing.model_router import get_model_for_intent
from app.observability.tracker import get_tracker


AGENT_NAME = "Resolution"
AGENT_DESCRIPTION = (
    "Synthesizes investigation findings into action proposals, manages "
    "human approval gates, executes approved actions, and generates "
    "final response summaries."
)


# ─────────────────────────────────────────────────────────────
# Node: Action Proposal (triggers HITL)
# ─────────────────────────────────────────────────────────────

@traceable(name="propose_action")
async def propose_action(state: AgentState, config: dict | None = None) -> dict:
    """Synthesize all findings and propose an action.
    
    Uses the SMART model for critical reasoning.
    """
    llm = get_model_for_intent("propose_action", state.get("model_provider"))
    
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
- tier_change: Change subscription tier (specify target tier in description, e.g. "Change to pro plan")
- suspend: Suspend customer account
- reactivate: Reactivate a suspended/cancelled customer account
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
    elif action.get("type") in ("refund", "credit", "tier_change", "suspend", "reactivate"):
        # No real customer found but LLM proposed a mutating action — force escalate
        action["type"] = "escalate"
        action["customer_id"] = None
        action["customer_name"] = "Not Found"
        action["description"] = f"Customer not found in database — escalating for manual review. Original proposal: {action.get('description', '')}"
        action["reason"] = "Cannot execute actions for unverified customers."
    
    return {
        "proposed_action": action,
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"✓ [{AGENT_NAME}] Proposed action: {action.get('type', 'unknown')} — {action.get('description', '')}"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node: HITL Interrupt — Wait for Human Approval
# ─────────────────────────────────────────────────────────────

@traceable(name="await_approval")
async def await_approval(state: AgentState, config: dict | None = None) -> dict:
    """Pause the workflow and wait for human approval.
    
    This is the core HITL mechanism (Flex 1).
    The LangGraph interrupt() function literally pauses execution
    and waits for a resume command with the human's decision.
    """
    action = state.get("proposed_action", {})
    
    # Non-destructive actions can auto-approve
    auto_approve_types = {"resolve", "reactivate"}
    if action.get("type") in auto_approve_types:
        return {
            "approval_status": "approved",
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"✓ [{AGENT_NAME}] Auto-approved: {action.get('type')} is non-destructive"
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
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"{'✓' if approved else '✗'} [{AGENT_NAME}] Human decision: {status}" + (f" — {reason}" if reason else "")
        ],
    }


def should_execute(state: AgentState) -> str:
    """Conditional edge: execute action if approved, generate response if denied."""
    if state.get("approval_status") == "approved":
        return "execute_action"
    return "generate_response"


# ─────────────────────────────────────────────────────────────
# Node: Action Execution (recommendation-only, no DB writes)
# ─────────────────────────────────────────────────────────────


@traceable(name="execute_action")
async def execute_action(state: AgentState, config: dict | None = None) -> dict:
    """Execute the approved action (recommendation-only — no database writes).

    Returns a descriptive result string based on the proposed action type.
    The system is intentionally read-only: actions are recommendations, not mutations.
    """
    action = state.get("proposed_action", {})
    action_type = action.get("type", "unknown")
    customer_name = action.get("customer_name", "Unknown")
    amount = action.get("amount") or 0

    results = {
        "refund": f"Refund of ${amount:.2f} recommended for {customer_name}. Awaiting finance team processing.",
        "credit": f"Account credit of ${amount:.2f} recommended for {customer_name}. Awaiting finance team processing.",
        "tier_change": f"Plan change recommended for {customer_name}. Awaiting account team processing.",
        "suspend": f"Account suspension recommended for {customer_name}. Awaiting compliance team processing.",
        "reactivate": f"Account reactivation recommended for {customer_name}. Awaiting account team processing.",
        "escalate": f"Ticket escalated to senior support manager for {customer_name}.",
        "resolve": "Ticket resolved. No further action required.",
    }
    result = results.get(action_type, "Action completed.")

    # Track in observability
    tracker = get_tracker()
    metrics = tracker.get_request(state["thread_id"])
    if metrics:
        metrics.approved = True

    return {
        "execution_result": result,
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"✓ [{AGENT_NAME}] Action executed: {result}"
        ],
    }


# ─────────────────────────────────────────────────────────────
# Node: Final Response Generation
# ─────────────────────────────────────────────────────────────

@traceable(name="generate_response")
async def generate_response(state: AgentState, config: dict | None = None) -> dict:
    """Generate a final human-readable summary response."""
    
    # If validate_customer already set a final_response (not found, mismatch, etc.),
    # preserve it — don't let the LLM overwrite it with hallucinated content.
    if state.get("final_response") and state.get("customer_found") is False:
        return {
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"✓ [{AGENT_NAME}] Response already set by validation — skipping LLM generation"
            ],
        }
    
    # If SQL returned 0 records, generate a clear "not found" response without LLM
    sql_result = state.get("sql_result", [])
    if not state.get("sql_error") and len(sql_result) == 0 and state.get("customer_found") is True:
        return {
            "final_response": f"No matching billing or transaction records were found for Customer #{state.get('user_message', '')}. "
                              f"The database query returned 0 results. This could mean the reported issue doesn't have a matching record, "
                              f"or the details provided may need clarification.",
            "active_agent": AGENT_NAME,
            "thought_log": state.get("thought_log", []) + [
                f"⚠ [{AGENT_NAME}] No records found in database — no action required"
            ],
        }
    
    llm = get_model_for_intent("generate_response", state.get("model_provider"))
    
    action = state.get("proposed_action", {})
    approved = state.get("approval_status") == "approved"
    execution = state.get("execution_result", "")
    denied_reason = state.get("denial_reason", "")
    sql_data = json.dumps(state.get("sql_result", []), indent=2, default=str)
    docs = state.get("docs_context", "None")
    
    # Extract customer details from the action proposal
    customer_name = action.get("customer_name", "Unknown")
    customer_id = action.get("customer_id", "N/A")
    
    messages = [
        SystemMessage(content="You are a support engineer writing a brief resolution summary. "
                      "Use the ACTUAL customer name, ticket details, and action results provided below. "
                      "NEVER use placeholder text like '[insert ticket number]' or '[customer name]'. "
                      "Be professional and concise. 2-3 sentences max."),
        HumanMessage(content=f"""Customer: {customer_name} (ID: {customer_id})
Original issue: {state['user_message']}
Intent: {state.get('intent', 'general')}

Database records:
{sql_data[:2000]}

Internal documentation:
{docs[:1000]}

Proposed action: {action.get('type', 'none')} — {action.get('description', 'None')}
Action reason: {action.get('reason', 'N/A')}
Action amount: ${action.get('amount', 0) or 0:.2f}
Action status: {'Approved and executed' if approved else f'Denied by manager — {denied_reason}' if denied_reason else 'Denied by manager'}
Execution result: {execution if approved else 'N/A'}

Write a brief resolution summary using the real data above:"""),
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
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"✓ [{AGENT_NAME}] Generated resolution summary"
        ],
    }
