"""Aegis as an A2A (Agent2Agent protocol v1.0) server.

Mounted on the main FastAPI app:

    GET  /.well-known/agent-card.json   discovery
    POST /a2a                           JSON-RPC: SendMessage, SendStreamingMessage,
                                        GetTask, CancelTask, SubscribeToTask
                                        (v1.0; v0.3 `message/send` etc. when the
                                        A2A-Version header is absent)

See docs/a2a.md for the task lifecycle and the trust model.
"""

from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    DefaultServerCallContextBuilder,
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore, TaskStore
from a2a.types.a2a_pb2 import Task
from a2a.utils.errors import UnsupportedOperationError
from fastapi import FastAPI

from app.a2a_server.card import RPC_PATH, build_agent_card
from app.a2a_server.executor import AegisAgentExecutor, thread_id_for
from app.config import get_settings
from app.observability.tracker import get_tracker
from app.ratelimit import RateLimiter

MAX_TASKS = 500  # same bound as the web thread store


class BoundedTaskStore(TaskStore):
    """In-memory task store that evicts the oldest task, and its graph checkpoint, when full."""

    def __init__(self, graph, max_tasks: int = MAX_TASKS):
        self.graph = graph
        self.max_tasks = max_tasks
        self._store = InMemoryTaskStore()
        self._owners: dict[str, ServerCallContext] = {}  # task_id → saving context, oldest first

    async def save(self, task: Task, context: ServerCallContext) -> None:
        await self._store.save(task, context)
        self._owners.setdefault(task.id, context)
        while len(self._owners) > self.max_tasks:
            task_id, owner = next(iter(self._owners.items()))
            del self._owners[task_id]
            await self._store.delete(task_id, owner)
            self.graph.checkpointer.delete_thread(thread_id_for(task_id))
            get_tracker().forget(thread_id_for(task_id))

    async def get(self, task_id: str, context: ServerCallContext) -> Task | None:
        return await self._store.get(task_id, context)

    async def list(self, params, context: ServerCallContext):
        return await self._store.list(params, context)

    async def delete(self, task_id: str, context: ServerCallContext) -> None:
        self._owners.pop(task_id, None)
        await self._store.delete(task_id, context)


class AegisRequestHandler(DefaultRequestHandler):
    """Task ids are capabilities, like web thread ids: there is no way to enumerate them.

    Anonymous callers all share one owner scope, so ListTasks would hand every
    caller every pending approval. It is switched off rather than scoped by IP.
    """

    async def on_list_tasks(self, params, context):
        raise UnsupportedOperationError(message="ListTasks is disabled: task ids are capabilities.")


class ClientAwareContextBuilder(DefaultServerCallContextBuilder):
    """Adds the peer address so the executor can apply the per-client rate limit."""

    def build(self, request) -> ServerCallContext:
        context = super().build(request)
        context.state["client_host"] = request.client.host if request.client else None
        return context


def mount_a2a(app: FastAPI, graph, rate_limiter: RateLimiter) -> None:
    settings = get_settings()
    card = build_agent_card(
        public_url=settings.public_api_url,
        version=app.version,
        approver_token_required=bool(settings.a2a_approver_token),
    )
    handler = AegisRequestHandler(
        agent_executor=AegisAgentExecutor(graph, rate_limiter, settings.a2a_approver_token),
        task_store=BoundedTaskStore(graph),
        agent_card=card,
    )
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(card),
        jsonrpc_routes=create_jsonrpc_routes(
            handler,
            rpc_url=RPC_PATH,
            context_builder=ClientAwareContextBuilder(),
            enable_v0_3_compat=True,
        ),
    )
