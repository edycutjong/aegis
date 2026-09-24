"""Spend protection for the public demo.

Two independent limits, both in-process (the demo runs as one instance):

- Per-client sliding window — keeps one visitor from monopolising the demo.
- Global daily cap — the hard ceiling on LLM spend. Client identity comes from
  proxy headers and can be spoofed, so the per-client window is a courtesy;
  this cap is the guarantee.

Only POST /api/chat is limited: it is the only endpoint that starts LLM work.
Approvals resume an already-paid-for thread.
"""

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    per_client: int
    window_seconds: int
    daily_cap: int
    _hits: dict[str, deque] = field(default_factory=dict)
    _day: int = -1
    _day_count: int = 0

    def check(self, client: str, now: float | None = None) -> tuple[bool, str, int]:
        """Record an attempt. Returns (allowed, reason, retry_after_seconds)."""
        now = time.time() if now is None else now

        day = int(now // 86400)
        if day != self._day:
            self._day, self._day_count = day, 0
        if self._day_count >= self.daily_cap:
            retry = int((day + 1) * 86400 - now) + 1
            return False, "The live demo has reached its daily ticket budget. It resets at 00:00 UTC.", retry

        hits = self._hits.setdefault(client, deque())
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        if len(hits) >= self.per_client:
            retry = int(hits[0] + self.window_seconds - now) + 1
            return False, f"Easy there. The demo allows {self.per_client} tickets every {self.window_seconds // 60} minutes per visitor.", retry

        hits.append(now)
        self._day_count += 1

        # Drop idle clients so the map cannot grow without bound.
        if len(self._hits) > 10_000:
            cutoff = now - self.window_seconds
            for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
                del self._hits[key]

        return True, "", 0


def client_key(headers, fallback: str | None) -> str:
    """Best-effort client identity behind a reverse proxy."""
    real = headers.get("x-real-ip")
    if real:
        return real.strip()
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return fallback or "unknown"
