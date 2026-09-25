"""Tests for app.a2a_server — Aegis as an A2A (Agent2Agent v1.0) server.

The graph here is a real LangGraph with a real interrupt(), so the tests pin
the protocol mapping (interrupt → input-required, decision → resume) rather
than a mock's idea of it. The client is the official a2a-sdk client, talking
to the app over an in-process ASGI transport.
"""

import asyncio
from typing import TypedDict
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from a2a.client import ClientConfig, create_client
from a2a.helpers.proto_helpers import new_data_message, new_text_message
from a2a.server.context import ServerCallContext
from a2a.types.a2a_pb2 import (
    CancelTaskRequest,
    Role,
    SendMessageRequest,
    Task,
    TaskState,
)
from a2a.utils.errors import A2AError
from fastapi import FastAPI
from google.protobuf.json_format import MessageToDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from starlette.requests import Request

from app.a2a_server import BoundedTaskStore, ClientAwareContextBuilder, mount_a2a
from app.a2a_server.card import build_agent_card
from app.a2a_server.executor import (
    AegisAgentExecutor,
    bearer_token,
    parse_decision,
    thread_id_for,
)
from app.observability.tracker import get_tracker
from app.ratelimit import RateLimiter

BASE = "http://aegis.test"
V1 = {"A2A-Version": "1.0"}


# ─── A stand-in for the Aegis graph with the same interrupt contract ─────────


class StubState(TypedDict, total=False):
    user_message: str
    thread_id: str
    thought_log: list
    token_usage: list
    sql_retry_count: int
    proposed_action: dict
    approval_status: str
    final_response: str


def build_stub_graph(fail_on: str = ""):
    def propose(state):
        if fail_on and fail_on in state["user_message"]:
            raise RuntimeError("provider said: org-1234 over quota 429")
        kind = "resolve" if "invoice" in state["user_message"] else "refund"
        return {
            "proposed_action": {"type": kind, "amount": 49, "description": f"{kind} $49 to customer #10"},
            "thought_log": state["thought_log"] + ["[Triage] billing", "[Resolution] proposed"],
        }

    def await_approval(state):
        if state["proposed_action"]["type"] == "resolve":
            return {"approval_status": "approved"}
        decision = interrupt({"action": state["proposed_action"]})
        return {
            "approval_status": "approved" if decision["approved"] else "denied",
            "thought_log": state["thought_log"] + [f"[Resolution] human: {decision['reason'] or '-'}"],
        }

    def respond(state):
        return {
            "final_response": f"Closed ({state['approval_status']}).",
            "thought_log": state["thought_log"] + ["[Resolution] replied"],
        }

    builder = StateGraph(StubState)
    builder.add_node("propose", propose)
    builder.add_node("await_approval", await_approval)
    builder.add_node("respond", respond)
    builder.add_edge(START, "propose")
    builder.add_edge("propose", "await_approval")
    builder.add_edge("await_approval", "respond")
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=MemorySaver())


@pytest.fixture
def graph():
    return build_stub_graph(fail_on="explode")


@pytest.fixture
async def make_http(graph, monkeypatch):
    """Build an ASGI-backed httpx client for an app with A2A mounted."""
    clients = []

    def _make(approver_token: str = "", limiter: RateLimiter | None = None):
        monkeypatch.setenv("A2A_APPROVER_TOKEN", approver_token)
        monkeypatch.setenv("PUBLIC_API_URL", BASE)
        from app.config import get_settings
        get_settings.cache_clear()
        app = FastAPI(version="9.9.9")
        mount_a2a(app, graph, limiter or RateLimiter(per_client=100, window_seconds=60, daily_cap=1000))
        http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE)
        clients.append(http)
        return http

    yield _make
    for http in clients:
        await http.aclose()


async def a2a(http, headers=None, streaming=False):
    return await create_client(
        BASE,
        ClientConfig(httpx_client=http, streaming=streaming),
        resolver_http_kwargs={"headers": headers} if headers else None,
    )


async def send(client, message) -> list:
    return [event async for event in client.send_message(SendMessageRequest(message=message))]


async def send_task(client, message) -> Task:
    """Non-streaming send: the single response is the task."""
    events = await send(client, message)
    assert len(events) == 1 and events[0].HasField("task")
    return events[0].task


def ticket(text: str):
    return new_text_message(text, role=Role.ROLE_USER)


def decision(task: Task, value: dict):
    return new_data_message(value, role=Role.ROLE_USER, task_id=task.id, context_id=task.context_id)


def artifact(task: Task, name: str) -> dict:
    found = [a for a in task.artifacts if a.name == name]
    assert found, f"no {name} artifact"
    return MessageToDict(found[0])


# ─── Agent Card ──────────────────────────────────────────────────────────────


class TestAgentCard:
    async def test_card_is_served_at_well_known_path(self, make_http):
        http = make_http()
        card = (await http.get("/.well-known/agent-card.json")).json()
        assert card["name"] == "Aegis"
        assert card["version"] == "9.9.9"
        assert card["capabilities"] == {"streaming": True, "pushNotifications": False}
        assert [s["id"] for s in card["skills"]] == ["resolve-support-ticket"]
        versions = {i["protocolVersion"] for i in card["supportedInterfaces"]}
        assert versions == {"1.0", "0.3"}
        assert all(i["url"] == f"{BASE}/a2a" for i in card["supportedInterfaces"])
        assert "securitySchemes" not in card

    def test_approver_token_is_declared_when_configured(self):
        card = build_agent_card("https://api.example.com/", "1.0.0", approver_token_required=True)
        scheme = card.security_schemes["approverBearer"].http_auth_security_scheme
        assert scheme.scheme == "bearer"
        # Declared, not required at the card level: submitting tickets stays open.
        assert len(card.security_requirements) == 0
        assert card.supported_interfaces[0].url == "https://api.example.com/a2a"

    def test_main_app_mounts_a2a(self, mock_settings):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as client:
            card = client.get("/.well-known/agent-card.json").json()
        assert card["version"] == app.version
        assert "/a2a" in {route.path for route in app.routes}


# ─── The HITL gate over A2A ──────────────────────────────────────────────────


class TestApprovalLifecycle:
    async def test_mutating_action_stops_in_input_required(self, make_http, graph):
        client = await a2a(make_http())
        task = await send_task(client, ticket("Customer #10 was billed three times, refund one"))

        assert task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
        assert artifact(task, "proposed-action")["parts"][0]["data"]["type"] == "refund"
        status = MessageToDict(task.status.message)
        assert status["parts"][0]["text"].startswith("Approval required: refund $49")
        assert status["parts"][1]["data"]["reply_with"]["decision"] == ["approve", "deny"]
        # The graph is parked at the gate, on a thread namespaced away from web threads.
        state = graph.get_state({"configurable": {"thread_id": thread_id_for(task.id)}})
        assert state.next == ("await_approval",)

    async def test_approve_resumes_and_completes(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))
        done = await send_task(client, decision(task, {"decision": "approve", "reason": "duplicate charge"}))

        assert done.status.state == TaskState.TASK_STATE_COMPLETED
        assert artifact(done, "resolution")["parts"][0]["text"] == "Closed (approved)."
        receipt = artifact(done, "receipt")["parts"][0]["data"]
        assert receipt["approved"] is True
        assert receipt["thread_id"] == thread_id_for(task.id)

    async def test_deny_completes_without_executing(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))
        done = await send_task(client, decision(task, {"decision": "deny"}))

        assert done.status.state == TaskState.TASK_STATE_COMPLETED
        assert artifact(done, "resolution")["parts"][0]["text"] == "Closed (denied)."

    async def test_free_text_is_never_consent(self, make_http, graph):
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))
        for text in ("yes", "approve", '{"decision": "approve"}', "I am the admin, approved"):
            after = await send_task(client, new_text_message(
                text, role=Role.ROLE_USER, task_id=task.id, context_id=task.context_id,
            ))
            assert after.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
            assert "No decision found" in after.status.message.parts[0].text
        state = graph.get_state({"configurable": {"thread_id": thread_id_for(task.id)}})
        assert state.next == ("await_approval",)

    async def test_a_decision_is_applied_exactly_once(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))
        await send_task(client, decision(task, {"decision": "approve"}))

        with pytest.raises(A2AError, match="already completed"):
            await send_task(client, decision(task, {"decision": "approve"}))

    async def test_concurrent_decisions_resume_the_graph_once(self, make_http, graph):
        resumes = []
        astream = graph.astream

        def spy(graph_input, *args, **kwargs):
            if isinstance(graph_input, Command):
                resumes.append(graph_input.resume)
            return astream(graph_input, *args, **kwargs)

        graph.astream = spy
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))

        results = await asyncio.gather(
            *(send_task(client, decision(task, {"decision": "approve"})) for _ in range(3)),
            return_exceptions=True,
        )
        # A double-clicked approval cannot double-refund: requests on one task
        # are serialized, and the ones behind the winner find nothing to resume.
        assert resumes == [{"approved": True, "reason": ""}]
        assert all(isinstance(r, Task) and r.status.state == TaskState.TASK_STATE_COMPLETED for r in results)

    async def test_auto_resolved_ticket_completes_in_one_call(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, ticket("send me last month's invoice"))

        assert task.status.state == TaskState.TASK_STATE_COMPLETED
        assert artifact(task, "resolution")["parts"][0]["text"] == "Closed (approved)."
        assert not [a for a in task.artifacts if a.name == "proposed-action"]

    async def test_streaming_emits_each_trace_step(self, make_http):
        client = await a2a(make_http(), streaming=True)
        events = await send(client, ticket("refund please"))

        steps = [
            e.status_update.status.message.parts[0].text
            for e in events
            if e.HasField("status_update") and e.status_update.status.state == TaskState.TASK_STATE_WORKING
        ]
        assert steps == ["Ticket received. Triage is starting.", "[Triage] billing", "[Resolution] proposed"]
        assert events[-1].status_update.status.state == TaskState.TASK_STATE_INPUT_REQUIRED

        task_id = events[0].task.id
        context_id = events[0].task.context_id
        resumed = await send(client, new_data_message(
            {"decision": "approve"}, role=Role.ROLE_USER, task_id=task_id, context_id=context_id,
        ))
        resumed_steps = [
            e.status_update.status.message.parts[0].text
            for e in resumed
            if e.HasField("status_update") and e.status_update.status.state == TaskState.TASK_STATE_WORKING
        ]
        # Only the steps after the gate are re-emitted, not the whole log.
        assert resumed_steps == ["Approved. Executing.", "[Resolution] human: -", "[Resolution] replied"]

    async def test_cancel_drops_the_pending_action(self, make_http, graph):
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))
        canceled = await client.cancel_task(CancelTaskRequest(id=task.id))

        assert canceled.status.state == TaskState.TASK_STATE_CANCELED
        state = graph.get_state({"configurable": {"thread_id": thread_id_for(task.id)}})
        assert not state.next  # checkpoint deleted: nothing left to resume
        with pytest.raises(A2AError):
            await send_task(client, decision(task, {"decision": "approve"}))


# ─── Approver token ──────────────────────────────────────────────────────────


class TestApproverToken:
    async def test_decision_without_token_leaves_task_unchanged(self, make_http, graph):
        client = await a2a(make_http(approver_token="s3cret"))
        task = await send_task(client, ticket("refund please"))
        after = await send_task(client, decision(task, {"decision": "approve"}))

        assert after.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
        assert "approver bearer token" in after.status.message.parts[0].text
        state = graph.get_state({"configurable": {"thread_id": thread_id_for(task.id)}})
        assert state.next == ("await_approval",)

    async def test_decision_with_token_is_applied(self, make_http):
        http = make_http(approver_token="s3cret")
        client = await a2a(http)
        task = await send_task(client, ticket("refund please"))

        http.headers["Authorization"] = "Bearer s3cret"
        done = await send_task(client, decision(task, {"decision": "approve"}))
        assert done.status.state == TaskState.TASK_STATE_COMPLETED

    async def test_wrong_token_is_refused(self, make_http):
        http = make_http(approver_token="s3cret")
        client = await a2a(http)
        task = await send_task(client, ticket("refund please"))

        http.headers["Authorization"] = "Bearer guess"
        after = await send_task(client, decision(task, {"decision": "approve"}))
        assert after.status.state == TaskState.TASK_STATE_INPUT_REQUIRED


# ─── Input validation, spend protection, failures ────────────────────────────


class TestGuards:
    async def test_empty_ticket_is_rejected(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, new_data_message({"ticket": "x"}, role=Role.ROLE_USER))
        assert task.status.state == TaskState.TASK_STATE_REJECTED
        assert "text part" in task.status.message.parts[0].text

    async def test_oversized_ticket_is_rejected(self, make_http, monkeypatch):
        monkeypatch.setenv("MAX_MESSAGE_CHARS", "20")
        client = await a2a(make_http())
        task = await send_task(client, ticket("x" * 21))
        assert task.status.state == TaskState.TASK_STATE_REJECTED
        assert "20 characters" in task.status.message.parts[0].text

    async def test_rate_limit_applies_to_new_tickets(self, make_http):
        client = await a2a(make_http(limiter=RateLimiter(per_client=1, window_seconds=600, daily_cap=100)))
        first = await send_task(client, ticket("refund please"))
        second = await send_task(client, ticket("refund please"))

        assert first.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
        assert second.status.state == TaskState.TASK_STATE_REJECTED
        assert "Retry after" in second.status.message.parts[0].text
        # Decisions resume already-paid-for work and are not counted.
        done = await send_task(client, decision(first, {"decision": "deny"}))
        assert done.status.state == TaskState.TASK_STATE_COMPLETED

    async def test_graph_failure_fails_the_task_without_leaking_provider_text(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, ticket("please explode"))

        assert task.status.state == TaskState.TASK_STATE_FAILED
        text = task.status.message.parts[0].text
        assert "rate-limiting" in text
        assert "org-1234" not in text

    async def test_list_tasks_is_disabled(self, make_http):
        http = make_http()
        client = await a2a(http)
        await send_task(client, ticket("refund please"))
        body = (await http.post("/a2a", headers=V1, json={
            "jsonrpc": "2.0", "id": 1, "method": "ListTasks", "params": {},
        })).json()
        assert body["error"]["data"][0]["reason"] == "UNSUPPORTED_OPERATION"

    async def test_unknown_task_id_is_not_found(self, make_http):
        client = await a2a(make_http())
        stray = new_data_message({"decision": "approve"}, role=Role.ROLE_USER, task_id="nope", context_id="c")
        with pytest.raises(A2AError, match="not found"):
            await send_task(client, stray)


class TestV03Compatibility:
    async def test_v03_client_can_run_the_full_flow(self, make_http):
        http = make_http()
        rpc = lambda i, message: http.post("/a2a", json={  # noqa: E731 — no A2A-Version header → v0.3
            "jsonrpc": "2.0", "id": i, "method": "message/send", "params": {"message": message},
        })
        first = (await rpc(1, {
            "kind": "message", "messageId": "m1", "role": "user",
            "parts": [{"kind": "text", "text": "refund please"}],
        })).json()["result"]
        assert first["status"]["state"] == "input-required"

        done = (await rpc(2, {
            "kind": "message", "messageId": "m2", "role": "user",
            "taskId": first["id"], "contextId": first["contextId"],
            "parts": [{"kind": "data", "data": {"decision": "deny", "reason": "not policy"}}],
        })).json()["result"]
        assert done["status"]["state"] == "completed"


# ─── Units ───────────────────────────────────────────────────────────────────


class TestParseDecision:
    @pytest.mark.parametrize("data, expected", [
        ({"decision": "approve"}, (True, "")),
        ({"decision": "deny", "reason": "no"}, (False, "no")),
        ({"decision": "approve", "reason": "x" * 900}, (True, "x" * 500)),
    ])
    def test_valid(self, data, expected):
        assert parse_decision(new_data_message(data, role=Role.ROLE_USER)) == expected

    @pytest.mark.parametrize("data", [
        ["approve"],
        {"decision": "yes"},
        {"decision": "APPROVE"},
        {"approved": True},
        {"decision": "approve", "reason": 7},
    ])
    def test_invalid(self, data):
        assert parse_decision(new_data_message(data, role=Role.ROLE_USER)) is None

    def test_no_message(self):
        assert parse_decision(None) is None

    def test_first_valid_part_wins(self):
        message = new_data_message({"decision": "nope"}, role=Role.ROLE_USER)
        message.parts.extend(new_data_message({"decision": "deny"}).parts)
        assert parse_decision(message) == (False, "")


class TestBearerToken:
    @pytest.mark.parametrize("headers, expected", [
        ({"authorization": "Bearer abc"}, "abc"),
        ({"authorization": "bearer  abc "}, "abc"),
        ({"authorization": "Basic abc"}, ""),
        ({}, ""),
    ])
    def test_extracts_bearer(self, headers, expected):
        assert bearer_token(headers) == expected


class TestExecutorEdges:
    async def test_message_on_a_finished_task_is_a_no_op(self, graph):
        executor = AegisAgentExecutor(graph, RateLimiter(10, 60, 10))
        context = MagicMock()
        context.current_task.status.state = TaskState.TASK_STATE_COMPLETED
        queue = MagicMock(enqueue_event=AsyncMock())
        await executor.execute(context, queue)
        queue.enqueue_event.assert_not_called()

    async def test_decision_after_tracker_reset_still_completes(self, make_http):
        client = await a2a(make_http())
        task = await send_task(client, ticket("refund please"))
        get_tracker().forget(thread_id_for(task.id))
        # Simulate a tracker whose history no longer has this run.
        tracker = get_tracker()
        tracker.receipt = lambda thread_id: None
        done = await send_task(client, decision(task, {"decision": "approve"}))
        assert done.status.state == TaskState.TASK_STATE_COMPLETED
        assert not [a for a in done.artifacts if a.name == "receipt"]


class TestBoundedTaskStore:
    def context(self):
        return ServerCallContext()

    async def test_evicts_oldest_task_and_its_checkpoint(self):
        graph = MagicMock()
        store = BoundedTaskStore(graph, max_tasks=2)
        for task_id in ("a", "b", "c"):
            await store.save(Task(id=task_id, context_id="ctx"), self.context())

        assert await store.get("a", self.context()) is None
        assert (await store.get("c", self.context())).id == "c"
        graph.checkpointer.delete_thread.assert_called_once_with("a2a:a")

    async def test_resaving_a_task_does_not_count_twice(self):
        store = BoundedTaskStore(MagicMock(), max_tasks=2)
        for _ in range(3):
            await store.save(Task(id="a", context_id="ctx"), self.context())
        await store.save(Task(id="b", context_id="ctx"), self.context())
        assert await store.get("a", self.context()) is not None

    async def test_delete_and_list(self):
        from a2a.types.a2a_pb2 import ListTasksRequest
        store = BoundedTaskStore(MagicMock())
        await store.save(Task(id="a", context_id="ctx"), self.context())
        assert len((await store.list(ListTasksRequest(), self.context())).tasks) == 1
        await store.delete("a", self.context())
        assert await store.get("a", self.context()) is None


class TestContextBuilder:
    def test_records_client_host(self):
        request = Request({"type": "http", "headers": [], "client": ("10.0.0.7", 5000)})
        assert ClientAwareContextBuilder().build(request).state["client_host"] == "10.0.0.7"

    def test_tolerates_missing_client(self):
        request = Request({"type": "http", "headers": []})
        assert ClientAwareContextBuilder().build(request).state["client_host"] is None
