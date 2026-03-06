"""Observability and cost tracking.

Flex 4: Track exactly how many tokens agents burn.
"The average cost to resolve a complex ticket is exactly $0.012."

Architecture Note:
    Current: In-memory storage (resets on restart) — sufficient for demos.
    Production: Persist to Redis TimeSeries for real-time dashboards,
    or Postgres/TimescaleDB for historical analytics, alerting on cost
    anomalies, and SLA tracking. The aggregate_stats() API surface
    stays identical — only the storage backend changes.
"""

import time
from dataclasses import dataclass, field

from app.routing.model_router import calculate_cost


@dataclass
class RequestMetrics:
    """Metrics for a single agent request."""
    thread_id: str
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    # Token tracking per step
    steps: list[dict] = field(default_factory=list)

    # Totals
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0

    # Model distribution
    models_used: dict[str, int] = field(default_factory=dict)  # model -> call count

    # Cache
    cache_hit: bool = False

    # Result
    approved: bool | None = None  # None = no HITL needed

    # HITL timing
    hitl_requested_at: float | None = None
    hitl_resolved_at: float | None = None

    def add_step(self, step_name: str, model: str, prompt_tokens: int, completion_tokens: int):
        """Record metrics for an LLM call."""
        cost = calculate_cost(model, prompt_tokens, completion_tokens)

        self.steps.append({
            "step": step_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost,
            "timestamp": time.time(),
        })

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost_usd += cost
        self.models_used[model] = self.models_used.get(model, 0) + 1

    def complete(self):
        """Mark the request as complete."""
        self.completed_at = time.time()

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or time.time()
        return round(end - self.started_at, 2)

    def to_dict(self) -> dict:
        """Serialize metrics for API response."""
        return {
            "thread_id": self.thread_id,
            "duration_seconds": self.duration_seconds,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "models_used": self.models_used,
            "steps": self.steps,
            "cache_hit": self.cache_hit,
            "approved": self.approved,
            "hitl_wait_seconds": round(self.hitl_resolved_at - self.hitl_requested_at, 2)
                if self.hitl_requested_at and self.hitl_resolved_at else None,
        }


class ObservabilityTracker:
    """Aggregates metrics across all requests."""

    def __init__(self):
        self.requests: dict[str, RequestMetrics] = {}
        self._history: list[dict] = []  # Completed requests

    def start_request(self, thread_id: str) -> RequestMetrics:
        """Start tracking a new request."""
        metrics = RequestMetrics(thread_id=thread_id)
        self.requests[thread_id] = metrics
        return metrics

    def get_request(self, thread_id: str) -> RequestMetrics | None:
        """Get metrics for a specific request."""
        return self.requests.get(thread_id)

    def complete_request(self, thread_id: str):
        """Move request to completed history."""
        if thread_id in self.requests:
            metrics = self.requests.pop(thread_id)
            metrics.complete()
            self._history.append(metrics.to_dict())

    def get_aggregate_stats(self, total_cache_hits: int = 0) -> dict:
        """Get aggregate statistics across all completed requests."""
        if not self._history:
            return {
                "total_requests": 0,
                "avg_cost_usd": 0.0,
                "avg_duration_seconds": 0.0,
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "model_distribution": {},
                "recent_requests": [],
            }

        total_cost = sum(r["total_cost_usd"] for r in self._history)
        total_tokens = sum(r["total_tokens"] for r in self._history)
        total_duration = sum(r["duration_seconds"] for r in self._history)
        n = len(self._history)

        # Aggregate model distribution
        model_dist: dict[str, int] = {}
        for r in self._history:
            for model, count in r["models_used"].items():
                model_dist[model] = model_dist.get(model, 0) + count

        # HITL approval rate
        hitl_requests = [r for r in self._history if r["approved"] is not None]
        hitl_approved = sum(1 for r in hitl_requests if r["approved"])
        hitl_rate = round((hitl_approved / len(hitl_requests) * 100), 1) if hitl_requests else None

        # HITL wait time
        hitl_waits = [r["hitl_wait_seconds"] for r in self._history if r.get("hitl_wait_seconds") is not None]
        avg_hitl_wait = round(sum(hitl_waits) / len(hitl_waits), 2) if hitl_waits else None

        # Cost saved by cache (avg cost of standard request × number of cache hits)
        avg_real_cost = (total_cost / n) if n > 0 else 0
        cost_saved = round(avg_real_cost * total_cache_hits, 6)

        return {
            "total_requests": n,
            "avg_cost_usd": round(total_cost / n, 6),
            "avg_duration_seconds": round(total_duration / n, 2),
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "model_distribution": model_dist,
            "recent_requests": self._history[-10:],
            "hitl_approval_rate": hitl_rate,
            "avg_hitl_wait_seconds": avg_hitl_wait,
            "cost_saved_by_cache": cost_saved,
        }


# Singleton
_tracker: ObservabilityTracker | None = None

def get_tracker() -> ObservabilityTracker:
    """Get the global tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = ObservabilityTracker()
    return _tracker
