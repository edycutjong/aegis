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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.agent.graph import agent_graph
from app.cache.semantic import get_cache
from app.db.supabase import get_supabase
from app.observability.tracker import get_tracker
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
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str | None = None  # Optional: resume existing thread


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


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Aegis",
        "description": "Autonomous Enterprise Action Engine",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def start_chat(request: ChatRequest):
    """Start a new agent workflow for a support ticket.

    1. Check semantic cache for duplicate queries
    2. If miss, start the LangGraph workflow
    3. Return thread_id for SSE streaming
    """
    # Check cache first (Flex 3)
    cache = await get_cache()
    cached = await cache.get(request.message)

    if cached:
        thread_id = cached.get("thread_id", str(uuid.uuid4()))
        return ChatResponse(
            thread_id=thread_id,
            status="cached",
            cache_hit=True,
        )

    # Generate thread ID
    thread_id = request.thread_id or str(uuid.uuid4())

    # Start observability tracking (Flex 4)
    tracker = get_tracker()
    tracker.start_request(thread_id)

    # Store thread metadata
    thread_store[thread_id] = {
        "message": request.message,
        "status": "processing",
        "thought_log": [],
        "proposed_action": None,
        "final_response": None,
    }

    # Start the agent workflow in background
    asyncio.create_task(_run_agent(thread_id, request.message))

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

        # Check if we hit an interrupt (HITL)
        state = agent_graph.get_state(config)
        if state.next:
            thread_store[thread_id]["status"] = "awaiting_approval"
        else:
            thread_store[thread_id]["status"] = "completed"
            # Cache the result — but only for successful resolutions (Flex 3)
            # Don't cache failures (customer not found, etc.) so retries hit fresh data
            final_resp = thread_store[thread_id].get("final_response")
            thought_log = thread_store[thread_id].get("thought_log", [])
            has_failure = any("✗" in t or "not found" in t.lower() for t in thought_log)
            if final_resp and not has_failure:
                cache = await get_cache()
                await cache.set(message, {
                    "thread_id": thread_id,
                    "response": final_resp,
                    "thought_log": thought_log,
                })
            # Complete observability tracking
            tracker = get_tracker()
            tracker.complete_request(thread_id)

    except Exception as e:
        thread_store[thread_id]["status"] = "error"
        thread_store[thread_id]["thought_log"].append(f"✗ Error: {str(e)}")
        print(f"[Agent Error] {thread_id}: {e}")


@app.get("/api/stream/{thread_id}")
async def stream_thoughts(thread_id: str):
    """SSE endpoint to stream agent thought process in real-time.

    The frontend connects to this immediately after POST /api/chat
    and receives step-by-step updates as the agent works.
    """

    async def event_generator():
        last_log_count = 0

        while True:
            thread = thread_store.get(thread_id)

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

            # Check for status changes
            status = thread.get("status", "processing")

            if status == "awaiting_approval":
                yield {
                    "event": "approval_required",
                    "data": json.dumps({
                        "action": thread.get("proposed_action"),
                        "message": "Human approval required",
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
                    }),
                }
                break

            elif status == "error":
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Agent workflow failed"}),
                }
                break

            await asyncio.sleep(0.3)  # Poll every 300ms  # pragma: no cover

    return EventSourceResponse(event_generator())


@app.post("/api/approve/{thread_id}", response_model=ApprovalResponse)
async def approve_action(thread_id: str, request: ApprovalRequest):
    """Resume the interrupted workflow with human approval/denial.

    Flex 1: HITL — This resumes the LangGraph interrupt.
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

        # Cache — only successful, approved resolutions
        # Skip cache for denied actions so the same request can be retried fresh
        final_resp = thread_store[thread_id].get("final_response")
        thought_log = thread_store[thread_id].get("thought_log", [])
        has_failure = any("✗" in t or "not found" in t.lower() for t in thought_log)
        if final_resp and not has_failure and request.approved:
            cache = await get_cache()
            await cache.set(thread["message"], {
                "thread_id": thread_id,
                "response": final_resp,
                "thought_log": thought_log,
            })

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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/thread/{thread_id}")
async def get_thread(thread_id: str):
    """Get the current state of a thread."""
    thread = thread_store.get(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@app.get("/api/metrics")
async def get_metrics():
    """Get observability metrics (Flex 4).

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
async def clear_cache():
    """Clear all cached responses from Redis.

    Removes all aegis:cache:* keys and resets hit/miss counters.
    """
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
                result[table] = {"count": 0, "latest": None, "error": res.get("error")}
        except Exception as e:
            result[table] = {"count": 0, "latest": None, "error": str(e)}

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
            raise HTTPException(status_code=500, detail=res.get("error", "Query failed"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            return {"traces": [], "error": f"Rate limit exceeded for LangSmith API. Traces will load after the rate limit resets (~5 minutes)." if "429" in error_str else error_str}


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
