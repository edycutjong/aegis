"""Triage Agent — Intent Classification.

The Triage Agent is the first responder in the Aegis multi-agent workflow.
It receives raw support tickets and classifies them into actionable categories
(billing, technical, account, general) using a fast/cheap LLM model.

This classification determines how downstream agents investigate the issue.
"""

import json
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.agent.state import AgentState
from app.routing.model_router import get_model
from app.observability.tracker import get_tracker


AGENT_NAME = "Triage"
AGENT_DESCRIPTION = (
    "Classifies incoming support tickets into categories (billing, technical, "
    "account, general) to route them to the correct investigation path."
)


@traceable(name="classify_intent")
async def classify_intent(state: AgentState, config: dict | None = None) -> dict:
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
        "active_agent": AGENT_NAME,
        "thought_log": state.get("thought_log", []) + [
            f"✓ [{AGENT_NAME}] Classified intent: {intent} (confidence: {confidence:.0%})"
        ],
    }
