"""Aegis — FastAPI server with SSE streaming and HITL endpoints.

The main entry point for the Autonomous Enterprise Action Engine.
"""

import asyncio
import json
import os
import time
import uuid
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.a2a_server import mount_a2a
from app.config import get_settings
from app.agent.graph import agent_graph
from app.cache.semantic import get_cache
from app.db.supabase import get_supabase
from app.errors import public_error
from app.observability.tracker import get_tracker
from app.ratelimit import RateLimiter, client_key
from langgraph.types import Command

# Suppress deprecated google.generativeai FutureWarning from langchain-google-genai
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")


# ─────────────────────────────────────────────────────────────
# Lifespan (startup/shutdown)
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Redis cache and LangSmith tracing on startup."""
    settings = get_settings()

    # Initialize LangSmith tracing — sets env vars that LangChain reads automatically
    if settings.langchain_tracing_v2 and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        print(f"🔭 LangSmith tracing enabled → project: {settings.langchain_project}")
    else:
        print("🔭 LangSmith tracing disabled (no API key or LANGCHAIN_TRACING_V2 != true)")

    cache = await get_cache()
    print("🛡️  Aegis backend started")  # pragma: no cover
    yield  # pragma: no cover
    await cache.close()
    print("🛡️  Aegis backend stopped")


# ─────────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Aegis — Autonomous Enterprise Action Engine",
    description="Multi-agent AI system with Human-in-the-Loop approval",
    version="2.0.1",  # x-release-please-version
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        *settings.cors_origins,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],  # lets the UI show a countdown on 429
)


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.max_message_chars)
    # No client-supplied thread id: ids are server-generated capabilities.


class ChatResponse(BaseModel):
    thread_id: str
    status: str  # processing, awaiting_approval, completed, cached
    cache_hit: bool = False


class ApprovalRequest(BaseModel):
    approved: bool
    reason: str = ""


class ApprovalResponse(BaseModel):
    thread_id: str
    status: str
    result: str | None = None


# ─────────────────────────────────────────────────────────────
# In-memory store for thread states (production: use Redis/DB)
# ─────────────────────────────────────────────────────────────

thread_store: dict[str, dict] = {}  # thread_id → metadata
MAX_THREADS = 500  # bound memory on a long-running demo; oldest threads are evicted first
STREAM_DEADLINE_S = 300  # an SSE stream never outlives a stuck run
_background_tasks: set[asyncio.Task] = set()

rate_limiter = RateLimiter(
    per_client=settings.rate_limit_per_client,
    window_seconds=settings.rate_limit_window_seconds,
    daily_cap=settings.daily_ticket_cap,
)


mount_a2a(app, agent_graph, rate_limiter)


def _evict_old_threads() -> None:
    """Drop the oldest threads once the store is full (dicts keep insertion order)."""
    while len(thread_store) >= MAX_THREADS:
        evicted = next(iter(thread_store))
        thread_store.pop(evicted)
        # Also free the LangGraph checkpoints and in-flight metrics.
        agent_graph.checkpointer.delete_thread(evicted)
        get_tracker().forget(evicted)


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Aegis",
        "description": "Autonomous Enterprise Action Engine",
        "version": "2.0.1",  # x-release-please-version
        "docs": "/docs",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def start_chat(request: ChatRequest, http_request: Request):
    """Start a new agent workflow for a support ticket.

    1. Check the response cache for a repeat of this exact ticket
    2. If miss, start the LangGraph workflow
    3. Return thread_id for SSE streaming
    """
    allowed, reason, retry_after = rate_limiter.check(
        client_key(http_request.headers, http_request.client.host if http_request.client else None)
    )
    if not allowed:
        raise HTTPException(status_code=429, detail=reason, headers={"Retry-After": str(retry_after)})

    thread_id = str(uuid.uuid4())
    _evict_old_threads()

    # A repeat of an auto-resolved ticket is served from the cache on a fresh
    # thread, so the reply renders even after the original thread is gone.
    cache = await get_cache()
    cached = await cache.get(request.message)
    if cached:
        thread_store[thread_id] = {
            "message": request.message,
            "status": "cached",
            "thought_log": cached.get("thought_log", []),
            "sql_attempts": cached.get("sql_attempts", []),
            "proposed_action": cached.get("proposed_action"),
            "final_response": cached.get("response"),
        }
        return ChatResponse(thread_id=thread_id, status="cached", cache_hit=True)

    get_tracker().start_request(thread_id)
    thread_store[thread_id] = {
        "message": request.message,
        "status": "processing",
        "thought_log": [],
        "proposed_action": None,
        "final_response": None,
    }

    # Keep a reference: the event loop only holds weak references to tasks,
    # so an unreferenced run can be garbage-collected mid-flight.
    task = asyncio.create_task(_run_agent(thread_id, request.message))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return ChatResponse(
        thread_id=thread_id,
        status="processing",
        cache_hit=False,
    )


async def _run_agent(thread_id: str, message: str):
    """Run the LangGraph agent workflow in the background."""
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "user_message": message,
        "thread_id": thread_id,
        "thought_log": [],
        "token_usage": [],
        "sql_retry_count": 0,
    }

    try:
        # Stream through the graph
        async for event in agent_graph.astream(initial_state, config, stream_mode="updates"):
            # Each event is {node_name: state_update}
            for node_name, update in event.items():
                if isinstance(update, dict):
                    # Update thread store with latest state
                    if "thought_log" in update:
                        thread_store[thread_id]["thought_log"] = update["thought_log"]
                    if "proposed_action" in update:
                        thread_store[thread_id]["proposed_action"] = update["proposed_action"]
                    if "final_response" in update:
                        thread_store[thread_id]["final_response"] = update["final_response"]
                    if "customer_candidates" in update:
                        thread_store[thread_id]["customer_candidates"] = update["customer_candidates"]
                    _record_sql(thread_store[thread_id], update)

        # Check if we hit an interrupt (HITL)
        state = agent_graph.get_state(config)
        if state.next:
            thread_store[thread_id]["status"] = "awaiting_approval"
        else:
            thread_store[thread_id]["status"] = "completed"
            # Don't cache failures (customer not found, etc.) so retries hit fresh data
            # Only auto-resolved answers are cached. Anything that went through
            # the approval gate is never replayed: a cached approved refund
            # would hand the next identical ticket a decision no human made.
            thread = thread_store[thread_id]
            final_resp = thread.get("final_response")
            thought_log = thread.get("thought_log", [])
            action_type = (thread.get("proposed_action") or {}).get("type")
            has_failure = any("✗" in t or "not found" in t.lower() for t in thought_log)
            if final_resp and action_type == "resolve" and not has_failure:
                cache = await get_cache()
                await cache.set(message, {
                    "response": final_resp,
                    "thought_log": thought_log,
                    "sql_attempts": thread.get("sql_attempts", []),
                    "proposed_action": thread.get("proposed_action"),
                })
            # Complete observability tracking
            tracker = get_tracker()
            tracker.complete_request(thread_id)

    except Exception as e:
        message = public_error(e)
        thread_store[thread_id]["status"] = "error"
        thread_store[thread_id]["error"] = message
        thread_store[thread_id]["thought_log"].append(f"✗ Error: {message}")
        print(f"[Agent Error] {thread_id}: {e}")  # full detail stays in server logs


def _record_sql(thread: dict, update: dict) -> None:
    """Keep every SQL attempt (query + outcome) so the UI can show self-healing."""
    attempts = thread.setdefault("sql_attempts", [])
    if "sql_query" in update and update["sql_query"]:
        attempts.append({"query": update["sql_query"], "error": None, "rows": None})
    if attempts and ("sql_error" in update or "sql_result" in update):
        last = attempts[-1]
        error = update.get("sql_error") or None
        last["error"] = str(error)[:300] if error else None
        last["rows"] = None if error else len(update.get("sql_result") or [])


@app.get("/api/stream/{thread_id}")
async def stream_thoughts(thread_id: str):
    """SSE endpoint to stream agent thought process in real-time.

    The frontend connects to this immediately after POST /api/chat
    and receives step-by-step updates as the agent works.
    """

    async def event_generator():
        last_log_count = 0
        last_sql = "[]"
        deadline = time.monotonic() + STREAM_DEADLINE_S

        while True:
            thread = thread_store.get(thread_id)

            if time.monotonic() > deadline:
                yield {"event": "error", "data": json.dumps({"error": "The run took too long and was abandoned."})}
                break

            if not thread:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Thread not found"}),
                }
                break

            # Send new thought log entries
            current_log = thread.get("thought_log", [])
            if len(current_log) > last_log_count:
                for entry in current_log[last_log_count:]:
                    yield {
                        "event": "thought",
                        "data": json.dumps({"step": entry}),
                    }
                last_log_count = len(current_log)

            sql_snapshot = json.dumps(thread.get("sql_attempts", []))
            if sql_snapshot != last_sql:
                last_sql = sql_snapshot
                yield {"event": "sql", "data": json.dumps({"attempts": thread.get("sql_attempts", [])})}

            # Check for status changes
            status = thread.get("status", "processing")

            if status == "awaiting_approval":
                yield {
                    "event": "approval_required",
                    "data": json.dumps({
                        "action": thread.get("proposed_action"),
                        "message": "Human approval required",
                        "sql_attempts": thread.get("sql_attempts", []),
                    }),
                }
                break

            elif status == "completed":
                yield {
                    "event": "completed",
                    "data": json.dumps({
                        "response": thread.get("final_response"),
                        "thought_log": current_log,
                        "customer_candidates": thread.get("customer_candidates"),
                        "sql_attempts": thread.get("sql_attempts", []),
                    }),
                }
                break

            elif status == "error":
                yield {
                    "event": "error",
                    "data": json.dumps({"error": thread.get("error") or "Agent workflow failed"}),
                }
                break

            await asyncio.sleep(0.3)  # Poll every 300ms  # pragma: no cover

    return EventSourceResponse(event_generator())


@app.post("/api/approve/{thread_id}", response_model=ApprovalResponse)
async def approve_action(thread_id: str, request: ApprovalRequest):
    """Resume the interrupted workflow with human approval/denial.

    This resumes the LangGraph interrupt with the human's decision.
    """
    thread = thread_store.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if thread.get("status") != "awaiting_approval":
        raise HTTPException(status_code=400, detail="Thread not awaiting approval")

    config = {"configurable": {"thread_id": thread_id}}

    # Resume the LangGraph workflow with human decision
    thread_store[thread_id]["status"] = "processing"

    try:
        async for event in agent_graph.astream(
            Command(resume={"approved": request.approved, "reason": request.reason}),
            config,
            stream_mode="updates",
        ):
            for node_name, update in event.items():
                if isinstance(update, dict):
                    if "thought_log" in update:
                        thread_store[thread_id]["thought_log"] = update["thought_log"]
                    if "final_response" in update:
                        thread_store[thread_id]["final_response"] = update["final_response"]

        thread_store[thread_id]["status"] = "completed"

        # Approved decisions are never cached (see _run_agent).

        # Complete observability tracking
        tracker = get_tracker()
        metrics = tracker.get_request(thread_id)
        if metrics:
            metrics.approved = request.approved
        tracker.complete_request(thread_id)

        return ApprovalResponse(
            thread_id=thread_id,
            status="completed",
            result=thread_store[thread_id].get("final_response"),
        )

    except Exception as e:
        message = public_error(e)
        thread_store[thread_id]["status"] = "error"
        thread_store[thread_id]["error"] = message
        print(f"[Approve Error] {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=message)


@app.get("/api/thread/{thread_id}")
async def get_thread(thread_id: str):
    """Get the current state of a thread, plus its cost receipt.

    The id is an unguessable server-generated capability; only the visitor who
    started the run has it, so the per-run receipt is served here rather than
    in the public /api/metrics aggregate.
    """
    thread = thread_store.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {**thread, "receipt": get_tracker().receipt(thread_id)}


@app.get("/api/metrics")
async def get_metrics():
    """Get aggregate observability metrics.

    Returns token usage, cost analysis, and cache statistics.
    """
    tracker = get_tracker()
    cache = await get_cache()
    cache_stats = cache.get_stats()

    return {
        "agent_metrics": tracker.get_aggregate_stats(total_cache_hits=cache_stats["hits"]),
        "cache_metrics": cache_stats,
    }


@app.delete("/api/cache")
async def clear_cache(http_request: Request):
    """Clear all cached responses from Redis.

    Removes all aegis:cache:* keys and resets hit/miss counters. Shares the
    chat rate limit: clearing forces fresh (paid) runs.
    """
    allowed, reason, retry_after = rate_limiter.check(
        client_key(http_request.headers, http_request.client.host if http_request.client else None)
    )
    if not allowed:
        raise HTTPException(status_code=429, detail=reason, headers={"Retry-After": str(retry_after)})
    cache = await get_cache()
    deleted = await cache.clear()
    return {
        "status": "cleared",
        "keys_deleted": deleted,
    }


@app.get("/api/db-status")
async def db_status():
    """Return record counts and data freshness for all tables.

    Useful for verifying seed data is loaded and timestamps are current.
    """
    db = get_supabase()
    tables = {
        "customers": "SELECT COUNT(*) as count, MAX(created_at) as latest FROM customers",
        "billing": "SELECT COUNT(*) as count, MAX(created_at) as latest FROM billing",
        "support_tickets": "SELECT COUNT(*) as count, MAX(created_at) as latest FROM support_tickets",
        "internal_docs": "SELECT COUNT(*) as count FROM internal_docs",
    }
    result = {}
    for table, query in tables.items():
        try:
            res = await db.execute_sql(query)
            if res["success"] and res.get("data"):
                row = res["data"][0] if isinstance(res["data"], list) else res["data"]
                result[table] = {
                    "count": row.get("count", 0),
                    "latest": row.get("latest"),
                }
            else:
                print(f"[db-status] {table}: {res.get('error')}")
                result[table] = {"count": 0, "latest": None, "error": "Query failed"}
        except Exception as e:
            print(f"[db-status] {table}: {e}")
            result[table] = {"count": 0, "latest": None, "error": "Database unreachable"}

    return result


ALLOWED_TABLES = {"customers", "billing", "support_tickets", "internal_docs"}


@app.get("/api/tables/{name}")
async def get_table_data(name: str):
    """Return rows from a seed data table.

    Only allows reading from the four known tables.
    """
    if name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"Unknown table: {name}")

    db = get_supabase()
    query = f"SELECT * FROM {name} ORDER BY id LIMIT 100"
    try:
        res = await db.execute_sql(query)
        if res["success"]:
            return {"table": name, "rows": res.get("data", []) or []}
        else:
            print(f"[tables] {name}: {res.get('error')}")
            raise HTTPException(status_code=500, detail="Query failed")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[tables] {name}: {e}")
        raise HTTPException(status_code=500, detail="Database unreachable")


# Simple in-memory TTL cache for traces (avoid hammering LangSmith)
_traces_cache: dict = {"data": None, "ts": 0.0}
_TRACES_TTL = 300  # seconds — LangSmith free tier has strict rate limits


@app.get("/api/traces")
async def get_traces():
    """Fetch recent LangSmith trace runs for the Aegis project.

    Proxies the LangSmith API through the backend so the API key
    stays server-side.  Uses a 5-minute in-memory cache and
    sequential child-run fetches to avoid rate limits.
    """
    settings = get_settings()
    enabled = settings.langchain_tracing_v2 and bool(settings.langchain_api_key)

    if not enabled:
        return {"traces": [], "error": None}

    # Return cached data if fresh
    now = time.monotonic()
    if _traces_cache["data"] is not None and (now - _traces_cache["ts"]) < _TRACES_TTL:
        return _traces_cache["data"]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            from langsmith import Client

            client = Client()

            # Fetch root runs (sync → offload to thread)
            root_runs = await asyncio.to_thread(
                lambda: list(
                    client.list_runs(
                        project_name=settings.langchain_project,
                        is_root=True,
                        limit=5,
                    )
                )
            )

            # Fetch child runs sequentially to avoid rate limit bursts
            traces = []
            for run in root_runs:
                try:
                    # Fetch ALL descendants (children + grandchildren) via trace_id
                    # This is one API call instead of N+1 calls
                    all_descendants = await asyncio.to_thread(
                        lambda r=run: list(
                            client.list_runs(
                                project_name=settings.langchain_project,
                                trace_id=r.trace_id,
                                is_root=False,
                            )
                        )
                    )

                    # Map all descendants for lineage tracing
                    descendants_by_id = {str(d.id): d for d in all_descendants}
                    run_id_str = str(run.id)

                    def get_top_level_child(d_id: str) -> str | None:
                        curr = d_id
                        seen = set()
                        while curr and curr not in seen:
                            seen.add(curr)
                            curr_run = descendants_by_id.get(curr)
                            if not curr_run:
                                return None
                            if str(curr_run.parent_run_id) == run_id_str:
                                return curr
                            curr = str(curr_run.parent_run_id)
                        return None

                    # Separate direct children and map nested LLM runs to their top-level child
                    child_runs_raw = []
                    llm_runs_by_top_child: dict[str, list] = {}

                    for desc in all_descendants:
                        if str(desc.parent_run_id) == run_id_str:
                            child_runs_raw.append(desc)

                        if desc.run_type == "llm":
                            top_child_id = get_top_level_child(str(desc.id))
                            if top_child_id:
                                if top_child_id not in llm_runs_by_top_child:
                                    llm_runs_by_top_child[top_child_id] = []
                                llm_runs_by_top_child[top_child_id].append(desc)

                    child_runs_raw.sort(key=lambda r: r.start_time or run.start_time)
                except Exception:
                    child_runs_raw = []
                    llm_runs_by_top_child = {}

                child_runs = []
                for child in child_runs_raw:
                    latency_ms = 0
                    if child.end_time and child.start_time:
                        latency_ms = int(
                            (child.end_time - child.start_time).total_seconds() * 1000
                        )

                    total_tokens = 0
                    if child.total_tokens is not None:
                        total_tokens = child.total_tokens
                    elif (
                        hasattr(child, "token_usage")
                        and child.token_usage
                    ):
                        total_tokens = child.token_usage.get("total_tokens", 0)

                    # Extract model name from extra metadata
                    model = ""
                    if hasattr(child, "extra") and child.extra:
                        metadata = child.extra.get("metadata", {})
                        model = metadata.get("ls_model_name", "")
                        if not model:
                            invocation = child.extra.get("invocation_params", {})
                            model = invocation.get("model", invocation.get("model_name", ""))

                    # If model still empty, check deeply nested LLM runs
                    if not model:
                        child_id_str = str(child.id)
                        for llm_run in llm_runs_by_top_child.get(child_id_str, []):
                            if hasattr(llm_run, "extra") and llm_run.extra:
                                gc_meta = llm_run.extra.get("metadata", {})
                                model = gc_meta.get("ls_model_name", "")
                                if not model:
                                    gc_inv = llm_run.extra.get("invocation_params", {})
                                    model = gc_inv.get("model", gc_inv.get("model_name", ""))
                                if model:
                                    break

                    total_cost = 0.0
                    if child.total_cost is not None:
                        total_cost = float(child.total_cost)

                    child_runs.append({
                        "id": str(child.id),
                        "name": child.name or "unknown",
                        "status": child.status or "unknown",
                        "latency_ms": latency_ms,
                        "total_tokens": total_tokens,
                        "model": model,
                        "total_cost": total_cost,
                    })

                root_latency_ms = 0
                if run.end_time and run.start_time:
                    root_latency_ms = int(
                        (run.end_time - run.start_time).total_seconds() * 1000
                    )

                traces.append({
                    "id": str(run.id),
                    "name": run.name or "aegis-support-workflow",
                    "status": run.status or "unknown",
                    "latency_ms": root_latency_ms,
                    "total_tokens": run.total_tokens or 0,
                    "total_cost": float(run.total_cost) if run.total_cost else 0.0,
                    "start_time": run.start_time.isoformat() if run.start_time else None,
                    "child_runs": child_runs,
                })

            result = {"traces": traces, "error": None}
            _traces_cache["data"] = result
            _traces_cache["ts"] = time.monotonic()
            return result

        except Exception as e:
            error_str = str(e)
            # Retry on 429 rate limit errors
            if "429" in error_str and attempt < max_retries - 1:
                wait = 5 * (attempt + 1)  # 5s, 10s backoff
                print(f"⚠ LangSmith rate limit hit, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
                continue
            break

    if "429" in error_str:
        return {"traces": [], "error": "Rate limit exceeded for LangSmith API. Traces will load after the rate limit resets (~5 minutes)."}
    print(f"[traces] {error_str}")
    return {"traces": [], "error": "Could not load traces from LangSmith."}


@app.get("/api/tracing-status")
async def tracing_status():
    """Check LangSmith tracing status and connectivity."""
    settings = get_settings()
    enabled = settings.langchain_tracing_v2 and bool(settings.langchain_api_key)

    connected = False
    if enabled:
        try:
            from langsmith import Client
            client = Client()
            connected = client.info is not None
        except Exception:
            connected = False

    return {
        "enabled": enabled,
        "project": settings.langchain_project,
        "connected": connected,
    }


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    cache = await get_cache()
    return {
        "status": "healthy",
        "cache_connected": cache.redis is not None,
    }
