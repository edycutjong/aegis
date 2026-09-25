"""Tests for app.ratelimit — the public demo's spend protection."""

from app.ratelimit import RateLimiter, client_key


def _limiter(**kw):
    return RateLimiter(**{"per_client": 2, "window_seconds": 60, "daily_cap": 5, **kw})


def test_allows_up_to_the_per_client_limit_then_blocks():
    rl = _limiter()
    assert rl.check("a", now=1000)[0]
    assert rl.check("a", now=1001)[0]
    allowed, reason, retry = rl.check("a", now=1002)
    assert not allowed
    assert "2 tickets every 1 minutes" in reason
    assert retry == 59


def test_window_slides():
    rl = _limiter()
    rl.check("a", now=1000)
    rl.check("a", now=1001)
    assert rl.check("a", now=1061)[0]


def test_clients_are_independent():
    rl = _limiter()
    rl.check("a", now=1000)
    rl.check("a", now=1000)
    assert rl.check("b", now=1000)[0]


def test_daily_cap_is_global_and_resets_at_utc_midnight():
    rl = _limiter(per_client=100, daily_cap=3)
    for c in "abc":
        assert rl.check(c, now=86400 * 10 + 5)[0]
    allowed, reason, retry = rl.check("d", now=86400 * 10 + 6)
    assert not allowed
    assert "daily ticket budget" in reason
    assert retry == 86400 - 6 + 1
    assert rl.check("d", now=86400 * 11 + 1)[0]


def test_rejected_attempts_do_not_consume_budget():
    rl = _limiter(per_client=1, daily_cap=2)
    rl.check("a", now=1000)
    rl.check("a", now=1001)  # rejected by per-client window
    assert rl.check("b", now=1002)[0]


def test_idle_clients_are_pruned_when_map_is_large():
    rl = _limiter(per_client=1, daily_cap=100_000)
    rl._hits = {f"old{i}": __import__("collections").deque([0.0]) for i in range(10_001)}
    rl.check("fresh", now=1000)
    assert list(rl._hits) == ["fresh"]


def test_uses_real_time_by_default():
    assert _limiter().check("a")[0]


def test_client_key_prefers_proxy_headers():
    assert client_key({"x-real-ip": " 1.1.1.1 "}, "9.9.9.9") == "1.1.1.1"
    # The leftmost X-Forwarded-For entry is client-controlled, so it is ignored.
    assert client_key({"x-forwarded-for": "2.2.2.2, 10.0.0.1"}, "9.9.9.9") == "9.9.9.9"
    assert client_key({}, "9.9.9.9") == "9.9.9.9"
    assert client_key({}, None) == "unknown"
