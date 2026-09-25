"""The real compiled graph, end to end, with fake LLMs and a fake database.

Every other test patches `interrupt()` or `agent_graph` itself, so the claim the
README leads with (a mutating action pauses at a real LangGraph interrupt, and
nothing executes until a human resumes it) was only exercised by the paid evals.
These run the real graph, checkpointer and routing for free on every PR. Only
the model calls and the Supabase HTTP calls are replaced, with rows copied from
seed.sql. (Contributed by the external audit.)
"""

import uuid
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

from app.agent.graph import build_agent_graph

CUSTOMERS = {
    8: {"id": 8, "name": "David Martinez", "email": "david.m@fintech.app", "plan": "pro", "status": "active"},
    10: {"id": 10, "name": "Chris Johnson", "email": "chris.j@ecomshop.com", "plan": "pro", "status": "active"},
}
BILLING = {
    8: [  # seed.sql: two charges, the "(DUPLICATE)" one, and the pending refund for it
        {"id": 31, "customer_id": 8, "amount": 49.0, "type": "refund", "status": "pending",
         "description": "Duplicate charge refund"},
        {"id": 29, "customer_id": 8, "amount": 49.0, "type": "charge", "status": "completed",
         "description": "Pro plan - Monthly subscription (DUPLICATE)"},
        {"id": 18, "customer_id": 8, "amount": 49.0, "type": "charge", "status": "completed",
         "description": "Pro plan - Monthly subscription"},
    ],
    10: [
        {"id": 30, "customer_id": 10, "amount": 49.0, "type": "charge", "status": "completed",
         "description": "Pro plan - Monthly subscription (DUPLICATE)"},
        {"id": 20, "customer_id": 10, "amount": 49.0, "type": "charge", "status": "completed",
         "description": "Pro plan - Monthly subscription"},
    ],
}
DOCS = [
    {"id": 1, "title": "Refund Policy", "category": "billing",
     "content": "Duplicate charges should be refunded immediately upon verification."},
    {"id": 2, "title": "Escalation Procedures", "category": "general",
     "content": "Any data breach or security incident goes directly to Tier 3 and Security team."},
]


class FakeDB:
    def __init__(self, customer_id: int):
        self.customer_id = customer_id

    async def execute_sql(self, query: str) -> dict:
        # Both the validation lookup and the model's investigation query.
        return {"success": True, "data": [CUSTOMERS[self.customer_id]]}

    async def get_billing(self, customer_id: int, limit: int = 100) -> list[dict]:
        return BILLING.get(customer_id, [])

    async def list_docs(self, limit: int = 100) -> list[dict]:
        return DOCS

    async def list_customers(self, limit: int = 1000) -> list[dict]:
        return list(CUSTOMERS.values())

    async def search_customers(self, name_parts, limit: int = 5) -> list[dict]:
        return []  # pragma: no cover - every ticket here carries an ID


class FakeLLM:
    """Answers each step with a canned reply and records that it was asked."""

    def __init__(self, step: str, replies: dict[str, str], calls: list[str]):
        self.step, self.replies, self.calls = step, replies, calls

    async def ainvoke(self, messages):
        self.calls.append(self.step)
        return AIMessage(content=self.replies[self.step])


def replies(intent: str, action_json: str) -> dict[str, str]:
    return {
        "classify_intent": f'{{"intent": "{intent}", "confidence": 0.95}}',
        "write_sql": "SELECT id, name, plan, status FROM customers WHERE id = 8",
        "propose_action": action_json,
        "generate_response": "Summary for the customer.",
    }


async def drive(graph, graph_input, thread_id: str, customer_id: int, canned: dict, calls: list):
    config = {"configurable": {"thread_id": thread_id}}
    db = FakeDB(customer_id)

    def model_for(step):
        return lambda *args, **kwargs: FakeLLM(step, canned, calls)

    with patch("app.agent.agents.investigator.get_supabase", return_value=db), \
         patch("app.agent.agents.researcher.get_supabase", return_value=db), \
         patch("app.agent.agents.classifier.get_model", model_for("classify_intent")), \
         patch("app.agent.agents.investigator.get_model", model_for("write_sql")), \
         patch("app.agent.agents.resolver.get_model",
               side_effect=lambda task, *_: FakeLLM(task, canned, calls)):
        async for _ in graph.astream(graph_input, config, stream_mode="updates"):
            pass
    return graph.get_state(config)


def new_ticket(text: str, thread_id: str) -> dict:
    return {"user_message": text, "thread_id": thread_id, "thought_log": [], "token_usage": [], "sql_retry_count": 0}


REFUND = '{"type": "refund", "amount": 49, "description": "Refund the duplicate charge", "reason": "Duplicate"}'
TICKET_10 = "Customer #10 Chris Johnson was charged $49 twice for his Pro plan. Please refund the duplicate."


@pytest.mark.parametrize("approved", [True, False])
async def test_refund_pauses_at_a_real_interrupt_until_a_human_decides(approved):
    graph, calls, thread_id = build_agent_graph(), [], f"it-{uuid.uuid4()}"
    canned = replies("billing", REFUND)

    paused = await drive(graph, new_ticket(TICKET_10, thread_id), thread_id, 10, canned, calls)
    assert paused.next == ("await_approval",)
    assert paused.values["proposed_action"]["type"] == "refund"
    assert "execution_result" not in paused.values  # nothing ran before the human

    done = await drive(graph, Command(resume={"approved": approved, "reason": "checked"}),
                       thread_id, 10, canned, calls)
    assert done.next == ()
    assert done.values["approval_status"] == ("approved" if approved else "denied")
    assert ("execution_result" in done.values) is approved
    assert done.values["final_response"] == "Summary for the customer."


@pytest.mark.parametrize("ticket, intent, model_says", [
    ("Customer #8 David Martinez wants to upgrade from Pro to Enterprise.",
     "account", '{"type": "tier_change", "amount": null, "description": "Change to enterprise plan", "reason": "Asked"}'),
    ("Customer #8 David Martinez is reselling accounts against our terms. Please suspend him.",
     "account", '{"type": "suspend", "amount": null, "description": "Suspend account", "reason": "ToS violation"}'),
    ("Customer #8 David Martinez is cancelling Pro and wants to be sure he won't be charged again next month.",
     "billing", '{"type": "tier_change", "amount": null, "description": "Move to the free plan", "reason": "Cancel"}'),
])
async def test_a_past_refund_does_not_hijack_an_unrelated_ticket(ticket, intent, model_says):
    """Customer #8 has a pending "Duplicate charge refund". Tickets that aren't
    a duplicate-charge complaint go to the model and, here, to the gate."""
    graph, calls, thread_id = build_agent_graph(), [], f"it-{uuid.uuid4()}"
    state = await drive(graph, new_ticket(ticket, thread_id), thread_id, 8, replies(intent, model_says), calls)

    assert "propose_action" in calls
    assert state.next == ("await_approval",)
    assert "duplicate-charge refund" not in state.values["proposed_action"]["description"].lower()


async def test_a_new_double_charge_waits_for_a_person():
    """Failed before this fix: the ticket was closed as 'already resolved' with
    no model call and no human, because an older duplicate refund was on file."""
    graph, calls, thread_id = build_agent_graph(), [], f"it-{uuid.uuid4()}"
    ticket = "Customer #8 David Martinez was double-charged again this week: a new charge, not the one you already refunded."
    state = await drive(graph, new_ticket(ticket, thread_id), thread_id, 8, replies("billing", REFUND), calls)

    assert "propose_action" not in calls  # the pre-check answers, with context for the person
    assert state.next == ("await_approval",)
    action = state.values["proposed_action"]
    assert action["type"] == "escalate"
    assert "duplicate-charge refund already on file" in action["description"].lower()


async def test_a_leaked_key_report_the_model_resolves_still_waits_for_a_person():
    """Failed before this fix: the model's "your key has been rotated" resolve
    completed on its own, though nothing rotates keys."""
    graph, calls, thread_id = build_agent_graph(), [], f"it-{uuid.uuid4()}"
    ticket = "Customer #8 David Martinez reports his API key was exposed in a public GitHub repository and needs it rotated."
    model_says = ('{"type": "resolve", "amount": null, "description": "Inform the customer that their API key '
                  'has been rotated.", "reason": "Exposure reported."}')
    state = await drive(graph, new_ticket(ticket, thread_id), thread_id, 8, replies("technical", model_says), calls)

    assert state.next == ("await_approval",)
    assert state.values["proposed_action"]["type"] == "escalate"
    assert "final_response" not in state.values  # no reply went out
