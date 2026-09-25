"""Tests for app.main — FastAPI endpoints with mocked dependencies."""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked dependencies."""
    with patch.dict(os.environ, {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-key",
        "REDIS_URL": "redis://localhost:6379",
        "FRONTEND_URL": "http://localhost:3000",
    }, clear=False):
        from app.config import get_settings
        get_settings.cache_clear()

        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


class TestRootEndpoint:
    """GET / should return app info."""

    def test_returns_app_info(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Aegis"
        # release-please bumps the version; the test follows the single
        # source of truth instead of pinning a literal that breaks every release.
        from pathlib import Path
        expected = (Path(__file__).resolve().parents[2] / "version.txt").read_text().strip()
        assert data["version"] == expected
        assert "docs" in data


class TestHealthEndpoint:
    """GET /api/health should return health status."""

    def test_returns_status(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "cache_connected" in data


class TestMetricsEndpoint:
    """GET /api/metrics should return observability data."""

    def test_returns_metrics(self, client):
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "agent_metrics" in data
        assert "cache_metrics" in data


class TestClearCacheEndpoint:
    """DELETE /api/cache should clear all cached responses."""

    def test_clears_cache(self, client):
        mock_cache = AsyncMock()
        mock_cache.clear = AsyncMock(return_value=5)

        with patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache):
            response = client.delete("/api/cache")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cleared"
            assert data["keys_deleted"] == 5

    def test_clears_empty_cache(self, client):
        mock_cache = AsyncMock()
        mock_cache.clear = AsyncMock(return_value=0)

        with patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache):
            response = client.delete("/api/cache")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cleared"
            assert data["keys_deleted"] == 0


class TestThreadEndpoint:
    """GET /api/thread/{thread_id} should return thread state."""

    def test_not_found(self, client):
        response = client.get("/api/thread/nonexistent-id")
        assert response.status_code == 404

    def test_found(self, client):
        from app.main import thread_store
        thread_store["test-thread"] = {
            "message": "test",
            "status": "completed",
            "thought_log": ["✓ Done"],
            "proposed_action": None,
            "final_response": "All good",
        }
        response = client.get("/api/thread/test-thread")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["final_response"] == "All good"
        del thread_store["test-thread"]


class TestChatEndpoint:
    """POST /api/chat should start an agent workflow."""

    def test_returns_thread_id(self, client):
        with patch("app.main._run_agent", new_callable=AsyncMock):
            response = client.post("/api/chat", json={"message": "Help with billing"})
            assert response.status_code == 200
            data = response.json()
            assert "thread_id" in data
            assert data["status"] in ("processing", "cached")

    def test_client_cannot_choose_the_thread_id(self, client):
        """Regression (audit P0): a client-chosen id could overwrite another
        visitor's thread. Ids are server-generated capabilities."""
        import uuid
        with patch("app.main._run_agent", new_callable=AsyncMock):
            response = client.post("/api/chat", json={
                "message": "Help with billing",
                "thread_id": "my-custom-id",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["thread_id"] != "my-custom-id"
            uuid.UUID(data["thread_id"])

    def test_empty_message_returns_422(self, client):
        """Empty string should be rejected by min_length=1 validation."""
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client):
        """Missing request body should return 422."""
        response = client.post("/api/chat")
        assert response.status_code == 422

    def test_cache_hit_returns_cached(self, client):
        """Cache hit returns early with cached thread_id."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value={
            "response": "Cached response",
            "thought_log": ["✓ cached step"],
            "proposed_action": {"type": "resolve"},
        })

        with patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache):
            response = client.post("/api/chat", json={"message": "cached query"})
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cached"
            assert data["cache_hit"] is True
            # A fresh thread carries the cached reply, so it renders even when
            # the original thread is long gone.
            thread = client.get(f"/api/thread/{data['thread_id']}").json()
            assert thread["final_response"] == "Cached response"
            assert thread["thought_log"] == ["✓ cached step"]


class TestApproveEndpoint:
    """POST /api/approve/{thread_id} should handle HITL approval."""

    def test_thread_not_found(self, client):
        response = client.post(
            "/api/approve/nonexistent",
            json={"approved": True, "reason": ""},
        )
        assert response.status_code == 404

    def test_thread_not_awaiting(self, client):
        from app.main import thread_store
        thread_store["test-thread-2"] = {
            "message": "test",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }
        response = client.post(
            "/api/approve/test-thread-2",
            json={"approved": True, "reason": ""},
        )
        assert response.status_code == 400
        del thread_store["test-thread-2"]

    def test_approve_resumes_workflow(self, client):
        """Successful approval resume."""
        from app.main import thread_store

        thread_store["approval-test"] = {
            "message": "refund request",
            "status": "awaiting_approval",
            "thought_log": ["✓ Proposed refund"],
            "proposed_action": {"type": "refund", "amount": 29.99},
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"execute_action": {"thought_log": ["✓ Executed"], "final_response": "Refund done"}}

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()

        mock_tracker = MagicMock()
        mock_tracker.get_request.return_value = MagicMock()
        mock_tracker.complete_request = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            response = client.post(
                "/api/approve/approval-test",
                json={"approved": True, "reason": ""},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] == "Refund done"
        # Regression (audit P1): an approved decision is never cached, or the
        # next identical ticket would get a refund no human approved.
        mock_cache.set.assert_not_called()
        del thread_store["approval-test"]

    def test_deny_skips_cache(self, client):
        """Denied actions should NOT be cached so user can retry fresh."""
        from app.main import thread_store

        thread_store["deny-cache-test"] = {
            "message": "refund request",
            "status": "awaiting_approval",
            "thought_log": ["✓ Proposed refund"],
            "proposed_action": {"type": "refund", "amount": 29.99},
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"generate_response": {"thought_log": ["✗ Denied"], "final_response": "Action denied by manager"}}

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()

        mock_tracker = MagicMock()
        mock_tracker.get_request.return_value = MagicMock()
        mock_tracker.complete_request = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            response = client.post(
                "/api/approve/deny-cache-test",
                json={"approved": False, "reason": "Too expensive"},
            )

        assert response.status_code == 200
        # Cache should NOT be called for denied actions
        mock_cache.set.assert_not_called()
        del thread_store["deny-cache-test"]

    def test_approve_exception_returns_500(self, client):
        """Exception during approval raises 500."""
        from app.main import thread_store

        thread_store["error-approval"] = {
            "message": "error test",
            "status": "awaiting_approval",
            "thought_log": [],
            "proposed_action": {"type": "refund"},
            "final_response": None,
        }

        async def mock_astream_fail(*args, **kwargs):
            raise RuntimeError("Graph execution failed")
            yield  # Make it an async generator  # noqa: E501

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream_fail

        with patch("app.main.agent_graph", mock_graph):
            response = client.post(
                "/api/approve/error-approval",
                json={"approved": True, "reason": ""},
            )

        assert response.status_code == 500
        del thread_store["error-approval"]

    def test_approve_no_metrics_skips_approved_assignment(self, client):
        """When tracker.get_request returns None (metrics were
        never started, e.g. server restarted mid-flow), approve_action must
        not crash trying to set `.approved` on None — it should just skip it."""
        from app.main import thread_store

        thread_store["no-metrics-approval"] = {
            "message": "refund request",
            "status": "awaiting_approval",
            "thought_log": ["✓ Proposed refund"],
            "proposed_action": {"type": "refund", "amount": 10.0},
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"execute_action": {"thought_log": ["✓ Executed"], "final_response": "Refund done"}}

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()

        mock_tracker = MagicMock()
        mock_tracker.get_request.return_value = None  # No metrics found
        mock_tracker.complete_request = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            response = client.post(
                "/api/approve/no-metrics-approval",
                json={"approved": True, "reason": ""},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        mock_tracker.complete_request.assert_called_once_with("no-metrics-approval")
        del thread_store["no-metrics-approval"]


# ─────────────────────────────────────────────────────────────
# _run_agent tests
# ─────────────────────────────────────────────────────────────


class TestRunAgent:
    """Test the background _run_agent function."""

    @pytest.mark.asyncio
    async def test_run_agent_completes(self):
        """Full successful _run_agent flow."""
        from app.main import _run_agent, thread_store

        thread_store["agent-test"] = {
            "message": "test message",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"classify_intent": {"thought_log": ["✓ Classified"]}}
            yield {"propose_action": {"proposed_action": {"type": "resolve"}}}
            yield {"generate_response": {"final_response": "Done!", "thought_log": ["✓ Complete"]}}

        mock_state = MagicMock()
        mock_state.next = None  # No interrupt

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream
        mock_graph.get_state = MagicMock(return_value=mock_state)

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()

        mock_tracker = MagicMock()
        mock_tracker.complete_request = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            await _run_agent("agent-test", "test message")

        assert thread_store["agent-test"]["status"] == "completed"
        assert thread_store["agent-test"]["final_response"] == "Done!"
        mock_cache.set.assert_called_once()
        mock_tracker.complete_request.assert_called_once_with("agent-test")
        del thread_store["agent-test"]

    @pytest.mark.asyncio
    async def test_run_agent_interrupt(self):
        """Agent hits HITL interrupt."""
        from app.main import _run_agent, thread_store

        thread_store["interrupt-test"] = {
            "message": "refund",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"propose_action": {
                "proposed_action": {"type": "refund"},
                "thought_log": ["✓ Proposed"],
            }}

        mock_state = MagicMock()
        mock_state.next = ("await_approval",)  # Has next = interrupt

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream
        mock_graph.get_state = MagicMock(return_value=mock_state)

        with patch("app.main.agent_graph", mock_graph):
            await _run_agent("interrupt-test", "refund")

        assert thread_store["interrupt-test"]["status"] == "awaiting_approval"
        del thread_store["interrupt-test"]

    @pytest.mark.asyncio
    async def test_run_agent_error(self):
        """Agent workflow throws exception."""
        from app.main import _run_agent, thread_store

        thread_store["error-test"] = {
            "message": "test",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }

        async def mock_astream_fail(*args, **kwargs):
            raise RuntimeError("LLM API error")
            yield  # Make it an async generator  # noqa: E501

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream_fail

        with patch("app.main.agent_graph", mock_graph):
            await _run_agent("error-test", "test")

        assert thread_store["error-test"]["status"] == "error"
        assert any("Error" in t for t in thread_store["error-test"]["thought_log"])
        del thread_store["error-test"]

    @pytest.mark.asyncio
    async def test_run_agent_updates_customer_candidates(self):
        """customer_candidates update in thread store."""
        from app.main import _run_agent, thread_store

        thread_store["candidates-test"] = {
            "message": "test",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"validate_customer": {
                "customer_candidates": [{"id": 1}, {"id": 2}],
                "thought_log": ["✓ Found candidates"],
                "final_response": "Ambiguous",
            }}

        mock_state = MagicMock()
        mock_state.next = None

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream
        mock_graph.get_state = MagicMock(return_value=mock_state)

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()
        mock_tracker = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            await _run_agent("candidates-test", "test")

        assert thread_store["candidates-test"]["customer_candidates"] == [{"id": 1}, {"id": 2}]
        del thread_store["candidates-test"]

    @pytest.mark.asyncio
    async def test_run_agent_skips_cache_when_thought_log_has_failure(self):
        """has_failure=True should skip caching even though
        final_response is set — a 'not found'/'✗' entry means the result
        shouldn't be served to future identical queries."""
        from app.main import _run_agent, thread_store

        thread_store["failure-cache-test"] = {
            "message": "test",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"validate_customer": {
                "thought_log": ["✗ Customer #999 not found in database — stopping"],
                "final_response": "Customer #999 was not found in our database.",
            }}

        mock_state = MagicMock()
        mock_state.next = None

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream
        mock_graph.get_state = MagicMock(return_value=mock_state)

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.complete_request = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            await _run_agent("failure-cache-test", "test")

        assert thread_store["failure-cache-test"]["status"] == "completed"
        mock_cache.set.assert_not_called()
        mock_tracker.complete_request.assert_called_once_with("failure-cache-test")
        del thread_store["failure-cache-test"]

    @pytest.mark.asyncio
    async def test_run_agent_skips_cache_when_no_final_response(self):
        """final_resp falsy should skip caching, but observability
        tracking must still complete regardless."""
        from app.main import _run_agent, thread_store

        thread_store["no-response-test"] = {
            "message": "test",
            "status": "processing",
            "thought_log": [],
            "proposed_action": None,
            "final_response": None,
        }

        async def mock_astream(*args, **kwargs):
            yield {"classify_intent": {"thought_log": ["✓ Classified"]}}

        mock_state = MagicMock()
        mock_state.next = None

        mock_graph = MagicMock()
        mock_graph.astream = mock_astream
        mock_graph.get_state = MagicMock(return_value=mock_state)

        mock_cache = AsyncMock()
        mock_cache.set = AsyncMock()
        mock_tracker = MagicMock()
        mock_tracker.complete_request = MagicMock()

        with patch("app.main.agent_graph", mock_graph), \
             patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache), \
             patch("app.main.get_tracker", return_value=mock_tracker):
            await _run_agent("no-response-test", "test")

        assert thread_store["no-response-test"]["status"] == "completed"
        mock_cache.set.assert_not_called()
        mock_tracker.complete_request.assert_called_once_with("no-response-test")
        del thread_store["no-response-test"]


# ─────────────────────────────────────────────────────────────
# SSE streaming tests
# ─────────────────────────────────────────────────────────────


class TestStreamEndpoint:
    """GET /api/stream/{thread_id} should return SSE events."""

    def test_stream_not_found(self, client):
        """Thread not found."""
        response = client.get("/api/stream/nonexistent-id")
        assert response.status_code == 200
        text = response.text
        assert "error" in text

    def test_stream_completed(self, client):
        """Completed thread streams final event."""
        from app.main import thread_store
        thread_store["stream-done"] = {
            "message": "test",
            "status": "completed",
            "thought_log": ["✓ Done"],
            "proposed_action": None,
            "final_response": "All resolved",
        }
        response = client.get("/api/stream/stream-done")
        assert response.status_code == 200
        text = response.text
        assert "completed" in text
        assert "All resolved" in text
        del thread_store["stream-done"]

    def test_stream_error(self, client):
        """Errored thread streams error event."""
        from app.main import thread_store
        thread_store["stream-error"] = {
            "message": "test",
            "status": "error",
            "thought_log": ["✗ Error: kaboom"],
            "proposed_action": None,
            "final_response": None,
        }
        response = client.get("/api/stream/stream-error")
        assert response.status_code == 200
        text = response.text
        assert "error" in text
        del thread_store["stream-error"]

    def test_stream_awaiting_approval(self, client):
        """Thread awaiting approval streams approval_required."""
        from app.main import thread_store
        thread_store["stream-approval"] = {
            "message": "test",
            "status": "awaiting_approval",
            "thought_log": ["✓ Proposed"],
            "proposed_action": {"type": "refund", "amount": 29.99},
            "final_response": None,
        }
        response = client.get("/api/stream/stream-approval")
        assert response.status_code == 200
        text = response.text
        assert "approval_required" in text
        del thread_store["stream-approval"]


# ─────────────────────────────────────────────────────────────
# db-status & table-data endpoint tests
# ─────────────────────────────────────────────────────────────


class TestDbStatusEndpoint:
    """GET /api/db-status should return record counts and freshness."""

    def test_returns_counts_with_list_data(self, client):
        """Success path where data is a list."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": [{"count": 10, "latest": "2026-03-01T08:00:00Z"}],
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/db-status")
            assert response.status_code == 200
            data = response.json()
            # Should have all 4 tables
            assert "customers" in data
            assert "billing" in data
            assert "support_tickets" in data
            assert "internal_docs" in data
            assert data["customers"]["count"] == 10
            assert data["customers"]["latest"] == "2026-03-01T08:00:00Z"

    def test_returns_counts_with_dict_data(self, client):
        """Success path where data is a dict (not a list)."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": {"count": 5, "latest": "2026-03-01T00:00:00Z"},
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/db-status")
            assert response.status_code == 200
            data = response.json()
            assert data["customers"]["count"] == 5

    def test_handles_query_failure(self, client):
        """Success=False returns error info."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": "relation does not exist",
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/db-status")
            assert response.status_code == 200
            data = response.json()
            assert data["customers"]["count"] == 0
            assert data["customers"]["error"] == "Query failed"  # raw DB text stays in logs

    def test_handles_exception(self, client):
        """execute_sql throws exception."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/db-status")
            assert response.status_code == 200
            data = response.json()
            assert data["customers"]["count"] == 0
            assert data["customers"]["error"] == "Database unreachable"

    def test_handles_empty_data(self, client):
        """Success=True but empty data."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": None,
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/db-status")
            assert response.status_code == 200
            data = response.json()
            assert data["customers"]["count"] == 0


class TestGetTableDataEndpoint:
    """GET /api/tables/{name} should return rows from a seed table."""

    def test_returns_rows_on_success(self, client):
        """Successful query returns rows."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 200
            data = response.json()
            assert data["table"] == "customers"
            assert len(data["rows"]) == 2

    def test_returns_empty_rows_when_data_is_none(self, client):
        """Data is None, should return empty list."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": None,
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/billing")
            assert response.status_code == 200
            data = response.json()
            assert data["table"] == "billing"
            assert data["rows"] == []

    def test_emails_are_masked(self, client):
        """Regression (external audit): the public table viewer returned every customer's email."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": [
                {"id": 1, "name": "Sarah Chen", "email": "sarah.chen@megacorp.com"},
                {"id": 2, "name": "No Email", "email": None},
                {"id": 3, "name": "Odd", "email": "not-an-address"},
            ],
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            rows = client.get("/api/tables/customers").json()["rows"]
        assert [r["email"] for r in rows] == ["s***@megacorp.com", None, "not-an-address"]
        assert rows[0]["name"] == "Sarah Chen"

    def test_unknown_table_returns_400(self, client):
        """Unknown table name returns 400."""
        response = client.get("/api/tables/secret_table")
        assert response.status_code == 400
        assert "Unknown table" in response.json()["detail"]

    def test_query_failure_returns_500(self, client):
        """Query returns success=False."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": "permission denied",
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 500
            assert response.json()["detail"] == "Query failed"

    def test_reraises_http_exception(self, client):
        """HTTPException is re-raised without wrapping."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(side_effect=HTTPException(
            status_code=503, detail="Service unavailable"
        ))

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 503
            assert "Service unavailable" in response.json()["detail"]

    def test_general_exception_returns_500(self, client):
        """General Exception is caught and returns 500."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(side_effect=RuntimeError("Database crashed"))

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 500
            assert response.json()["detail"] == "Database unreachable"


class TestDemoProtection:
    """Spend protection for the public demo."""

    def test_rate_limited_request_returns_429_with_retry_after(self, client):
        from app import main as main_mod
        with patch.object(main_mod.rate_limiter, "check", return_value=(False, "slow down", 42)), \
             patch("app.main._run_agent", new_callable=AsyncMock) as run:
            response = client.post("/api/chat", json={"message": "Help with billing"})
        assert response.status_code == 429
        assert response.json()["detail"] == "slow down"
        assert response.headers["retry-after"] == "42"
        run.assert_not_called()

    def test_per_client_limit_trips_after_budget(self, client):
        from app import main as main_mod
        limit = main_mod.rate_limiter.per_client
        with patch("app.main._run_agent", new_callable=AsyncMock):
            codes = [
                client.post("/api/chat", json={"message": f"ticket {i}"}).status_code
                for i in range(limit + 1)
            ]
        assert codes[:limit] == [200] * limit
        assert codes[-1] == 429

    def test_overlong_message_is_rejected(self, client):
        response = client.post("/api/chat", json={"message": "x" * 5000})
        assert response.status_code == 422

    def test_thread_store_evicts_oldest(self):
        from app import main as main_mod
        saved = dict(main_mod.thread_store)
        try:
            main_mod.thread_store.clear()
            for i in range(main_mod.MAX_THREADS):
                main_mod.thread_store[f"t{i}"] = {}
            main_mod._evict_old_threads()
            assert "t0" not in main_mod.thread_store
            assert len(main_mod.thread_store) == main_mod.MAX_THREADS - 1
        finally:
            main_mod.thread_store.clear()
            main_mod.thread_store.update(saved)


def test_cors_origins_accepts_comma_separated_list(mock_settings):
    mock_settings.frontend_url = "https://aegis.vercel.app/, https://aegis.dev"
    assert mock_settings.cors_origins == ["https://aegis.vercel.app", "https://aegis.dev"]


class TestSqlVisibilityAndErrors:
    """The trace UI shows every SQL attempt; errors reaching the UI are sanitized."""

    def test_record_sql_tracks_attempts_and_outcomes(self):
        from app.main import _record_sql
        thread: dict = {}
        _record_sql(thread, {"sql_query": "SELECT bad FROM customers"})
        _record_sql(thread, {"sql_error": "column bad does not exist", "sql_result": []})
        _record_sql(thread, {"sql_query": "SELECT * FROM customers"})
        _record_sql(thread, {"sql_error": "", "sql_result": [{"id": 1}, {"id": 2}]})
        _record_sql(thread, {"thought_log": ["unrelated"]})
        assert thread["sql_attempts"] == [
            {"query": "SELECT bad FROM customers", "error": "column bad does not exist", "rows": None},
            {"query": "SELECT * FROM customers", "error": None, "rows": 2},
        ]

    def test_result_without_attempt_is_ignored(self):
        from app.main import _record_sql
        thread: dict = {}
        _record_sql(thread, {"sql_result": []})
        assert thread["sql_attempts"] == []

    @pytest.mark.parametrize("error,expected", [
        (Exception("Error code: 429 - org_01abc rate limit"), "rate-limiting"),
        (type("ResourceExhausted", (Exception,), {})("quota"), "rate-limiting"),
        (TimeoutError("timed out"), "timed out"),
        (ValueError("secret org_01abc detail"), "(ValueError)"),
    ])
    def test_public_error_never_leaks_provider_text(self, error, expected):
        from app.main import public_error
        message = public_error(error)
        assert expected in message
        assert "org_01abc" not in message

    def test_stream_emits_sql_snapshot_and_error_message(self, client):
        from app.main import thread_store
        thread_store["stream-err"] = {
            "message": "t", "status": "error", "thought_log": [],
            "sql_attempts": [{"query": "SELECT 1", "error": None, "rows": 1}],
            "error": "The model providers are rate-limiting this demo right now.",
        }
        text = client.get("/api/stream/stream-err").text
        del thread_store["stream-err"]
        assert "event: sql" in text
        assert "SELECT 1" in text
        assert "rate-limiting this demo" in text

    def test_stream_approval_includes_sql_attempts(self, client):
        from app.main import thread_store
        thread_store["stream-gate"] = {
            "message": "t", "status": "awaiting_approval", "thought_log": [],
            "proposed_action": {"type": "refund"},
            "sql_attempts": [{"query": "SELECT 2", "error": None, "rows": 0}],
        }
        text = client.get("/api/stream/stream-gate").text
        del thread_store["stream-gate"]
        assert "approval_required" in text and "SELECT 2" in text

    def test_retry_after_is_exposed_to_browsers(self, client):
        from app import main as main_mod
        with patch.object(main_mod.rate_limiter, "check", return_value=(False, "slow", 9)):
            response = client.post("/api/chat", json={"message": "x"}, headers={"Origin": "http://localhost:3000"})
        assert "retry-after" in response.headers.get("access-control-expose-headers", "").lower()


class TestAuditHardening:
    def test_stream_gives_up_after_deadline(self, client):
        from app import main as main_mod
        main_mod.thread_store["stuck"] = {"message": "t", "status": "processing", "thought_log": []}
        with patch.object(main_mod, "STREAM_DEADLINE_S", -1):
            text = client.get("/api/stream/stuck").text
        del main_mod.thread_store["stuck"]
        assert "took too long" in text

    def test_clearing_the_cache_is_rate_limited(self, client):
        from app import main as main_mod
        with patch.object(main_mod.rate_limiter, "check", return_value=(False, "slow", 5)):
            response = client.delete("/api/cache")
        assert response.status_code == 429

    def test_public_metrics_never_list_thread_ids(self):
        from app.observability.tracker import ObservabilityTracker
        tracker = ObservabilityTracker()
        tracker.start_request("secret-thread")
        tracker.complete_request("secret-thread")
        recent = tracker.get_aggregate_stats()["recent_requests"]
        assert recent and all("thread_id" not in r for r in recent)
        assert tracker.receipt("secret-thread")["thread_id"] == "secret-thread"

    def test_receipt_for_in_flight_and_unknown_runs(self):
        from app.observability.tracker import ObservabilityTracker
        tracker = ObservabilityTracker()
        tracker.start_request("live")
        assert tracker.receipt("live")["thread_id"] == "live"
        assert tracker.receipt("nope") is None
        tracker.forget("live")
        assert tracker.receipt("live") is None

    def test_history_is_bounded(self):
        from app.observability import tracker as tracker_mod
        tracker = tracker_mod.ObservabilityTracker()
        with patch.object(tracker_mod, "HISTORY_LIMIT", 3):
            for i in range(5):
                tracker.start_request(f"t{i}")
                tracker.complete_request(f"t{i}")
        assert [r["thread_id"] for r in tracker._history] == ["t2", "t3", "t4"]

    def test_eviction_frees_checkpoints_and_metrics(self):
        from app import main as main_mod
        saved = dict(main_mod.thread_store)
        try:
            main_mod.thread_store.clear()
            for i in range(main_mod.MAX_THREADS):
                main_mod.thread_store[f"t{i}"] = {}
            with patch.object(main_mod.agent_graph.checkpointer, "delete_thread") as delete, \
                 patch("app.main.get_tracker") as tracker:
                main_mod._evict_old_threads()
            delete.assert_called_once_with("t0")
            tracker.return_value.forget.assert_called_once_with("t0")
        finally:
            main_mod.thread_store.clear()
            main_mod.thread_store.update(saved)

    def test_thread_response_includes_receipt(self, client):
        from app import main as main_mod
        main_mod.thread_store["with-receipt"] = {"message": "t", "status": "completed", "thought_log": []}
        with patch("app.main.get_tracker") as tracker:
            tracker.return_value.receipt.return_value = {"total_cost_usd": 0.002}
            data = client.get("/api/thread/with-receipt").json()
        del main_mod.thread_store["with-receipt"]
        assert data["receipt"] == {"total_cost_usd": 0.002}


class TestErroredRunsLeaveTheTracker:
    """Regression (audit): a run that raised stayed "in flight" in the tracker
    until eviction, so /api/metrics counted failures as runs in progress."""

    @pytest.mark.asyncio
    async def test_failed_run_is_completed_as_errored(self):
        from app.main import _run_agent, thread_store
        from app.observability.tracker import get_tracker

        thread_store["errored-run"] = {"message": "m", "status": "processing", "thought_log": [],
                                       "proposed_action": None, "final_response": None}
        get_tracker().start_request("errored-run")

        async def fail(*args, **kwargs):
            raise RuntimeError("provider down")
            yield  # noqa: E501 — make it an async generator

        graph = MagicMock()
        graph.astream = fail
        with patch("app.main.agent_graph", graph):
            await _run_agent("errored-run", "m")

        stats = get_tracker().get_aggregate_stats()
        assert stats["in_flight_requests"] == 0
        assert stats["errored_requests"] == 1
        assert get_tracker().receipt("errored-run")["error"] is True
        del thread_store["errored-run"]

    def test_failed_approval_is_completed_as_errored(self, client):
        from app.main import thread_store
        from app.observability.tracker import get_tracker

        thread_store["errored-approval"] = {"message": "m", "status": "awaiting_approval", "thought_log": [],
                                            "proposed_action": {"type": "refund"}, "final_response": None}
        get_tracker().start_request("errored-approval")

        async def fail(*args, **kwargs):
            raise RuntimeError("provider down")
            yield  # noqa: E501 — make it an async generator

        graph = MagicMock()
        graph.astream = fail
        with patch("app.main.agent_graph", graph):
            assert client.post("/api/approve/errored-approval", json={"approved": True, "reason": ""}).status_code == 500

        stats = get_tracker().get_aggregate_stats()
        assert stats["in_flight_requests"] == 0
        assert stats["errored_requests"] == 1
        del thread_store["errored-approval"]

    def test_a_run_paused_at_the_gate_is_in_flight_not_errored(self):
        from app.observability.tracker import get_tracker
        tracker = get_tracker()
        tracker.start_request("paused").add_step("s", "gpt-4.1-mini", 1000, 100)
        stats = tracker.get_aggregate_stats()
        assert (stats["in_flight_requests"], stats["completed_requests"], stats["errored_requests"]) == (1, 0, 0)
        assert stats["total_cost_usd"] > 0


class TestLifespanTracing:
    """Startup turns LangSmith on only with both the flag and a key. The env
    is restored afterwards so no other test ever uploads traces."""

    @pytest.mark.asyncio
    async def test_tracing_enabled_sets_langchain_env(self):
        from app.config import Settings
        from app.main import app, lifespan

        settings = Settings()
        settings.langchain_tracing_v2 = True
        settings.langchain_api_key = "lsv2_test"
        settings.langchain_project = "aegis-test"
        cache = MagicMock(close=AsyncMock())
        with patch.dict(os.environ, {}, clear=False), \
             patch("app.main.get_settings", return_value=settings), \
             patch("app.main.get_cache", AsyncMock(return_value=cache)):
            async with lifespan(app):
                assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
                assert os.environ["LANGCHAIN_PROJECT"] == "aegis-test"
        assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"
