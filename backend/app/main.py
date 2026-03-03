"""Aegis — FastAPI server with SSE streaming and HITL endpoints.

The main entry point for the Autonomous Enterprise Action Engine.
"""

import asyncio
import json
import os
import uuid
import warnings
from contextlib import asynccontextmanager

# Suppress deprecated google.generativeai FutureWarning from langchain-google-genai
warnings.filterwarnings("ignore", category=FutureWarning, module="langchain_google_genai")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.agent.graph import agent_graph
from app.cache.semantic import get_cache
from app.observability.tracker import get_tracker
from langgraph.types import Command


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
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
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
        
        # Cache — only successful resolutions
        final_resp = thread_store[thread_id].get("final_response")
        thought_log = thread_store[thread_id].get("thought_log", [])
        has_failure = any("✗" in t or "not found" in t.lower() for t in thought_log)
        if final_resp and not has_failure:
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
    
    return {
        "agent_metrics": tracker.get_aggregate_stats(),
        "cache_metrics": cache.get_stats(),
    }


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
