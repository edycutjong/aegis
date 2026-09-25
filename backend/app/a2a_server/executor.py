"""Runs the Aegis LangGraph workflow as an A2A task.

The mapping is one-to-one with the web flow:

    ticket text        → new task, TASK_STATE_WORKING, one status update per trace step
    auto-resolved      → TASK_STATE_COMPLETED + `resolution` artifact
    interrupt()        → TASK_STATE_INPUT_REQUIRED + `proposed-action` artifact
    decision data part → Command(resume=...) → TASK_STATE_COMPLETED

The caller is another program, so the resume path is stricter than the UI's:
the decision must be a typed data part (free text is never read as consent)
and, when an approver token is configured, must carry it.
"""

import hmac
from typing import cast

from a2a.helpers.proto_helpers import (
    get_data_parts,
    new_data_part,
    new_message,
    new_text_message,
    new_task,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types.a2a_pb2 import Message, TaskState
from langgraph.types import Command

from app.config import get_settings
from app.errors import public_error
from app.observability.tracker import get_tracker
from app.ratelimit import RateLimiter, client_key

DECISIONS = {"approve": True, "deny": False}
MAX_REASON_CHARS = 500
DECISION_HELP = (
    'Reply on this task with a data part {"decision": "approve" | "deny", "reason": "..."}. '
    "Free text is not accepted as a decision."
)


def thread_id_for(task_id: str) -> str:
    """LangGraph thread for an A2A task, namespaced away from web-UI threads."""
    return f"a2a:{task_id}"


def parse_decision(message: Message | None) -> tuple[bool, str] | None:
    """Return (approved, reason) from the first well-formed decision part, else None."""
    if message is None:
        return None
    for data in get_data_parts(message.parts):
        if not isinstance(data, dict):
            continue
        decision = data.get("decision")
        if decision not in DECISIONS:
            continue
        reason = data.get("reason", "")
        if not isinstance(reason, str):
            continue
        return DECISIONS[decision], reason[:MAX_REASON_CHARS]
    return None


def bearer_token(headers: dict) -> str:
    auth = headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


class AegisAgentExecutor(AgentExecutor):
    def __init__(self, graph, rate_limiter: RateLimiter, approver_token: str = ""):
        self.graph = graph
        self.rate_limiter = rate_limiter
        self.approver_token = approver_token

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = self._updater(context, event_queue)
        task = context.current_task
        if task is None:
            await event_queue.enqueue_event(new_task(
                updater.task_id,
                updater.context_id,
                TaskState.TASK_STATE_SUBMITTED,
                history=[cast(Message, context.message)],
            ))
            await self._start(context, updater)
        elif task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
            await self._decide(context, updater)
        # Anything else (a message queued behind a run that has since finished)
        # is a no-op: the caller gets the task back unchanged.

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Abandon the task. A pending action is dropped, never executed."""
        updater = self._updater(context, event_queue)
        thread_id = thread_id_for(updater.task_id)
        self.graph.checkpointer.delete_thread(thread_id)
        get_tracker().forget(thread_id)
        await updater.cancel(self._text(updater, "Task canceled. No action was executed."))

    # ── new ticket ────────────────────────────────────────────

    async def _start(self, context: RequestContext, updater: TaskUpdater) -> None:
        ticket = context.get_user_input().strip()
        max_chars = get_settings().max_message_chars
        if not ticket:
            await updater.reject(self._text(updater, "Send the support ticket as a text part."))
            return
        if len(ticket) > max_chars:
            await updater.reject(self._text(updater, f"Tickets are limited to {max_chars} characters."))
            return

        state = context.call_context.state
        allowed, reason, retry_after = self.rate_limiter.check(
            client_key(state.get("headers", {}), state.get("client_host"))
        )
        if not allowed:
            await updater.reject(self._text(updater, f"{reason} Retry after {retry_after}s."))
            return

        thread_id = thread_id_for(updater.task_id)
        get_tracker().start_request(thread_id)
        await updater.start_work(self._text(updater, "Ticket received. Triage is starting."))
        initial_state = {
            "user_message": ticket,
            "thread_id": thread_id,
            "thought_log": [],
            "token_usage": [],
            "sql_retry_count": 0,
        }
        await self._run(initial_state, thread_id, updater)

    # ── human decision ────────────────────────────────────────

    async def _decide(self, context: RequestContext, updater: TaskUpdater) -> None:
        if self.approver_token:
            presented = bearer_token(context.call_context.state.get("headers", {}))
            if not hmac.compare_digest(presented.encode(), self.approver_token.encode()):
                await updater.requires_input(self._text(
                    updater,
                    "Approving or denying requires the approver bearer token. The task is unchanged.",
                ))
                return

        decision = parse_decision(context.message)
        if decision is None:
            await updater.requires_input(self._text(updater, f"No decision found. {DECISION_HELP}"))
            return

        approved, reason = decision
        thread_id = thread_id_for(updater.task_id)
        metrics = get_tracker().get_request(thread_id)
        if metrics:
            metrics.approved = approved
        await updater.start_work(self._text(updater, "Approved. Executing." if approved else "Denied. Closing out."))
        await self._run(Command(resume={"approved": approved, "reason": reason}), thread_id, updater)

    # ── shared ────────────────────────────────────────────────

    async def _run(self, graph_input, thread_id: str, updater: TaskUpdater) -> None:
        config = {"configurable": {"thread_id": thread_id}}
        values = self.graph.get_state(config).values if isinstance(graph_input, Command) else {}
        seen = len(values.get("thought_log", []))
        try:
            async for event in self.graph.astream(graph_input, config, stream_mode="updates"):
                for update in event.values():
                    if not isinstance(update, dict):
                        continue
                    log = update.get("thought_log") or []
                    for step in log[seen:]:
                        await updater.update_status(TaskState.TASK_STATE_WORKING, self._text(updater, step))
                    seen = max(seen, len(log))
        except Exception as e:
            print(f"[A2A Error] {thread_id}: {e}")  # full detail stays in server logs
            get_tracker().forget(thread_id)
            await updater.failed(self._text(updater, public_error(e)))
            return

        state = self.graph.get_state(config)
        if state.next:
            action = state.values.get("proposed_action") or {}
            await updater.add_artifact([new_data_part(action)], name="proposed-action")
            await updater.requires_input(new_message(
                [
                    new_text_part(f"Approval required: {action.get('description', action.get('type', 'action'))}"),
                    new_data_part({"proposed_action": action, "reply_with": {"decision": ["approve", "deny"], "reason": "string"}}),
                ],
                context_id=updater.context_id,
                task_id=updater.task_id,
            ))
            return

        response = state.values.get("final_response") or ""
        await updater.add_artifact([new_text_part(response)], name="resolution")
        tracker = get_tracker()
        tracker.complete_request(thread_id)
        receipt = tracker.receipt(thread_id)
        if receipt:
            await updater.add_artifact([new_data_part(receipt)], name="receipt")
        await updater.complete(self._text(updater, response))

    @staticmethod
    def _updater(context: RequestContext, event_queue: EventQueue) -> TaskUpdater:
        # The request handler assigns both ids before execute() or cancel() runs.
        return TaskUpdater(event_queue, cast(str, context.task_id), cast(str, context.context_id))

    @staticmethod
    def _text(updater: TaskUpdater, text: str) -> Message:
        return new_text_message(text, context_id=updater.context_id, task_id=updater.task_id)
