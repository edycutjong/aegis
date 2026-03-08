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
        assert data["version"] == "1.0.0"
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


class TestTracingStatusEndpoint:
    """GET /api/tracing-status should return LangSmith status."""

    def test_disabled_by_default(self, client):
        response = client.get("/api/tracing-status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "project" in data
        assert "connected" in data

    def test_enabled_with_env(self):
        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "test-project",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                response = c.get("/api/tracing-status")
                assert response.status_code == 200
                data = response.json()
                assert data["project"] == "test-project"

    def test_enabled_connected(self):
        """Cover L375-377: LangSmith enabled and client.info returns data."""
        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "test-project",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()

            mock_client = MagicMock()
            mock_client.info = {"version": "1.0"}

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/tracing-status")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["connected"] is True

    def test_lifespan_tracing_disabled(self):
        """Cover lifespan else branch (L45) when tracing is disabled."""
        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "false",
            "LANGCHAIN_API_KEY": "",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                response = c.get("/api/tracing-status")
                assert response.status_code == 200
                data = response.json()
                assert data["enabled"] is False

    def test_enabled_but_connection_fails(self):
        """Cover L376-377: LangSmith enabled but Client() raises."""
        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()

            with patch("langsmith.Client", side_effect=Exception("Connection failed")):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/tracing-status")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["connected"] is False


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

    def test_with_explicit_thread_id(self, client):
        with patch("app.main._run_agent", new_callable=AsyncMock):
            response = client.post("/api/chat", json={
                "message": "Help with billing",
                "thread_id": "my-custom-id",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["thread_id"] == "my-custom-id"

    def test_empty_message_returns_422(self, client):
        """Empty string should be rejected by min_length=1 validation."""
        response = client.post("/api/chat", json={"message": ""})
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client):
        """Missing request body should return 422."""
        response = client.post("/api/chat")
        assert response.status_code == 422

    def test_cache_hit_returns_cached(self, client):
        """Cover L130-136: cache hit returns early with cached thread_id."""
        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value={
            "thread_id": "cached-thread-id",
            "response": "Cached response",
        })

        with patch("app.main.get_cache", new_callable=AsyncMock, return_value=mock_cache):
            response = client.post("/api/chat", json={"message": "cached query"})
            assert response.status_code == 200
            data = response.json()
            assert data["thread_id"] == "cached-thread-id"
            assert data["status"] == "cached"
            assert data["cache_hit"] is True


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
        """Cover L295-334: Successful approval resume."""
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
        # Verify cache was called for approved action
        mock_cache.set.assert_called_once()
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
        """Cover L336-337: Exception during approval raises 500."""
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


# ─────────────────────────────────────────────────────────────
# _run_agent tests (L166-212)
# ─────────────────────────────────────────────────────────────


class TestRunAgent:
    """Test the background _run_agent function."""

    @pytest.mark.asyncio
    async def test_run_agent_completes(self):
        """Cover L166-207: Full successful _run_agent flow."""
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
        """Cover L194-195: Agent hits HITL interrupt."""
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
        """Cover L209-212: Agent workflow throws exception."""
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
        """Cover L189-190: customer_candidates update in thread store."""
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


# ─────────────────────────────────────────────────────────────
# SSE streaming tests (L223-279)
# ─────────────────────────────────────────────────────────────


class TestStreamEndpoint:
    """GET /api/stream/{thread_id} should return SSE events."""

    def test_stream_not_found(self, client):
        """Cover L229-234: thread not found."""
        response = client.get("/api/stream/nonexistent-id")
        assert response.status_code == 200
        text = response.text
        assert "error" in text

    def test_stream_completed(self, client):
        """Cover L259-268: completed thread streams final event."""
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
        """Cover L270-275: errored thread streams error event."""
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
        """Cover L249-257: thread awaiting approval streams approval_required."""
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
# db-status & table-data endpoint tests (L399-447)
# ─────────────────────────────────────────────────────────────


class TestDbStatusEndpoint:
    """GET /api/db-status should return record counts and freshness."""

    def test_returns_counts_with_list_data(self, client):
        """Cover L399-415: success path where data is a list."""
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
        """Cover L411: success path where data is a dict (not a list)."""
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
        """Cover L416-417: success=False returns error info."""
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
            assert data["customers"]["error"] == "relation does not exist"

    def test_handles_exception(self, client):
        """Cover L418-419: execute_sql throws exception."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/db-status")
            assert response.status_code == 200
            data = response.json()
            assert data["customers"]["count"] == 0
            assert data["customers"]["error"] == "Connection refused"

    def test_handles_empty_data(self, client):
        """Cover L410: success=True but empty data."""
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
        """Cover L436-441: successful query returns rows."""
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
        """Cover L441: data is None, should return empty list."""
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

    def test_unknown_table_returns_400(self, client):
        """Cover L433-434: unknown table name returns 400."""
        response = client.get("/api/tables/secret_table")
        assert response.status_code == 400
        assert "Unknown table" in response.json()["detail"]

    def test_query_failure_returns_500(self, client):
        """Cover L442-443: query returns success=False."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": "permission denied",
        })

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 500
            assert "permission denied" in response.json()["detail"]

    def test_reraises_http_exception(self, client):
        """Cover L444-445: HTTPException is re-raised without wrapping."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(side_effect=HTTPException(
            status_code=503, detail="Service unavailable"
        ))

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 503
            assert "Service unavailable" in response.json()["detail"]

    def test_general_exception_returns_500(self, client):
        """Cover L446-447: general Exception is caught and returns 500."""
        mock_db = AsyncMock()
        mock_db.execute_sql = AsyncMock(side_effect=RuntimeError("Database crashed"))

        with patch("app.main.get_supabase", return_value=mock_db):
            response = client.get("/api/tables/customers")
            assert response.status_code == 500
            assert "Database crashed" in response.json()["detail"]


# ─────────────────────────────────────────────────────────────
# /api/traces endpoint tests
# ─────────────────────────────────────────────────────────────


class TestTracesEndpoint:
    """GET /api/traces should proxy LangSmith trace data."""

    def test_traces_disabled_returns_empty(self):
        """When LangSmith is not configured, return empty traces."""
        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "false",
            "LANGCHAIN_API_KEY": "",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                response = c.get("/api/traces")
                assert response.status_code == 200
                data = response.json()
                assert data["traces"] == []
                assert data["error"] is None

    def test_traces_returns_data(self):
        """Cover the full success path with mocked LangSmith client."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            # Create mock child run
            mock_child = MagicMock()
            mock_child.id = "child-run-1"
            mock_child.parent_run_id = "root-run-1"
            mock_child.name = "classify_intent"
            mock_child.status = "success"
            mock_child.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_child.end_time = datetime(2026, 3, 5, 6, 0, 0, 180000, tzinfo=timezone.utc)
            mock_child.total_tokens = 312
            mock_child.total_cost = 0.0003
            mock_child.extra = {"metadata": {"ls_model_name": "groq/llama-3.3-70b"}}

            # Create mock child with no cost/tokens (execute_sql style)
            mock_child2 = MagicMock()
            mock_child2.id = "child-run-2"
            mock_child2.parent_run_id = "root-run-1"
            mock_child2.name = "execute_sql"
            mock_child2.status = "success"
            mock_child2.start_time = datetime(2026, 3, 5, 6, 0, 0, 200000, tzinfo=timezone.utc)
            mock_child2.end_time = datetime(2026, 3, 5, 6, 0, 0, 245000, tzinfo=timezone.utc)
            mock_child2.total_tokens = None
            mock_child2.total_cost = None
            mock_child2.extra = {"invocation_params": {"model": "supabase/postgres"}}
            # Simulate no token_usage attr
            del mock_child2.token_usage

            # Create mock root run
            mock_root = MagicMock()
            mock_root.id = "root-run-1"
            mock_root.trace_id = "root-run-1"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 3, 200000, tzinfo=timezone.utc)
            mock_root.total_tokens = 4218
            mock_root.total_cost = 0.0091

            mock_client = MagicMock()
            mock_client.list_runs = MagicMock(
                side_effect=[
                    [mock_root],
                    [mock_child, mock_child2],
                ]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["traces"]) == 1
                    assert data["error"] is None

                    trace = data["traces"][0]
                    assert trace["name"] == "aegis-support-workflow"
                    assert trace["total_tokens"] == 4218
                    assert trace["total_cost"] == 0.0091
                    assert len(trace["child_runs"]) == 2

                    child1 = trace["child_runs"][0]
                    assert child1["name"] == "classify_intent"
                    assert child1["total_tokens"] == 312
                    assert child1["model"] == "groq/llama-3.3-70b"

                    child2 = trace["child_runs"][1]
                    assert child2["name"] == "execute_sql"
                    assert child2["total_tokens"] == 0
                    assert child2["model"] == "supabase/postgres"

    def test_traces_with_token_usage_fallback(self):
        """Cover token_usage dict fallback when total_tokens is None."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            mock_child = MagicMock()
            mock_child.id = "child-tu"
            mock_child.parent_run_id = "root-tu"
            mock_child.name = "search_docs"
            mock_child.status = "success"
            mock_child.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_child.end_time = datetime(2026, 3, 5, 6, 0, 0, 400000, tzinfo=timezone.utc)
            mock_child.total_tokens = None
            mock_child.total_cost = 0.0009
            mock_child.extra = {"metadata": {}}
            mock_child.token_usage = {"total_tokens": 892}

            mock_root = MagicMock()
            mock_root.id = "root-tu"
            mock_root.trace_id = "root-tu"
            mock_root.name = None
            mock_root.status = None
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = None
            mock_root.total_tokens = None
            mock_root.total_cost = None

            mock_client = MagicMock()
            mock_client.list_runs = MagicMock(
                side_effect=[[mock_root], [mock_child]]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    data = response.json()
                    trace = data["traces"][0]
                    assert trace["name"] == "aegis-support-workflow"
                    assert trace["latency_ms"] == 0
                    assert trace["total_cost"] == 0.0

                    child = trace["child_runs"][0]
                    assert child["total_tokens"] == 892

    def test_traces_handles_exception(self):
        """Cover exception handling — should return error string."""
        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            with patch("langsmith.Client", side_effect=Exception("API unreachable")):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["traces"] == []
                    assert "API unreachable" in data["error"]

    def test_traces_returns_cached_data(self):
        """Cover L478: TTL cache hit returns cached data without calling LangSmith."""
        import time

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache

            # Pre-populate cache with fresh data (timestamp = now)
            cached_result = {"traces": [{"id": "cached-trace", "name": "cached"}], "error": None}
            _traces_cache["data"] = cached_result
            _traces_cache["ts"] = time.monotonic()

            from app.main import app
            with TestClient(app, raise_server_exceptions=False) as c:
                response = c.get("/api/traces")
                assert response.status_code == 200
                data = response.json()
                # Should return cached data directly
                assert data["traces"] == [{"id": "cached-trace", "name": "cached"}]
                assert data["error"] is None

            # Clean up
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

    def test_traces_invocation_params_model_name(self):
        """Cover model extraction from invocation_params.model_name fallback."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            mock_child = MagicMock()
            mock_child.id = "child-inv"
            mock_child.parent_run_id = "root-inv"
            mock_child.name = "propose_action"
            mock_child.status = "success"
            mock_child.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_child.end_time = datetime(2026, 3, 5, 6, 0, 0, 890000, tzinfo=timezone.utc)
            mock_child.total_tokens = 1106
            mock_child.total_cost = 0.0033
            mock_child.extra = {
                "metadata": {},
                "invocation_params": {"model_name": "gpt-4.1"},
            }

            mock_root = MagicMock()
            mock_root.id = "root-inv"
            mock_root.trace_id = "root-inv"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 3, tzinfo=timezone.utc)
            mock_root.total_tokens = 1106
            mock_root.total_cost = 0.0033

            mock_client = MagicMock()
            mock_client.list_runs = MagicMock(
                side_effect=[[mock_root], [mock_child]]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    data = response.json()
                    child = data["traces"][0]["child_runs"][0]
                    assert child["model"] == "gpt-4.1"

    def test_traces_grandchild_model_extraction(self):
        """Cover model extraction from grandchild LLM runs when child has none."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            # Child run (chain type) — no model info at this level
            mock_child = MagicMock()
            mock_child.id = "child-gc"
            mock_child.parent_run_id = "root-gc"
            mock_child.name = "classify_intent"
            mock_child.status = "success"
            mock_child.run_type = "chain"
            mock_child.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_child.end_time = datetime(2026, 3, 5, 6, 0, 0, 500000, tzinfo=timezone.utc)
            mock_child.total_tokens = 312
            mock_child.total_cost = 0.0003
            mock_child.extra = {"metadata": {}}  # No ls_model_name!

            # Grandchild run 1 (llm type) — has the model info in ls_model_name
            mock_grandchild = MagicMock()
            mock_grandchild.id = "grandchild-llm"
            mock_grandchild.parent_run_id = "child-gc"  # Parent is the child
            mock_grandchild.name = "ChatGroq"
            mock_grandchild.run_type = "llm"
            mock_grandchild.status = "success"
            mock_grandchild.start_time = datetime(2026, 3, 5, 6, 0, 0, 100000, tzinfo=timezone.utc)
            mock_grandchild.end_time = datetime(2026, 3, 5, 6, 0, 0, 400000, tzinfo=timezone.utc)
            mock_grandchild.total_tokens = 312
            mock_grandchild.total_cost = 0.0003
            mock_grandchild.extra = {"metadata": {"ls_model_name": "groq/llama-3.3-70b"}}

            # Child run 2 (chain type) — no model info
            mock_child2 = MagicMock()
            mock_child2.id = "child-gc-2"
            mock_child2.parent_run_id = "root-gc"
            mock_child2.name = "generate_response"
            mock_child2.status = "success"
            mock_child2.run_type = "chain"
            mock_child2.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_child2.end_time = datetime(2026, 3, 5, 6, 0, 0, 500000, tzinfo=timezone.utc)
            mock_child2.total_tokens = 500
            mock_child2.total_cost = 0.0005
            mock_child2.extra = {"metadata": {}}  # No ls_model_name!

            # Grandchild run 2 (llm type) — model info in invocation_params
            mock_grandchild2 = MagicMock()
            mock_grandchild2.id = "grandchild-llm-2"
            mock_grandchild2.parent_run_id = "child-gc-2"  # Parent is child 2
            mock_grandchild2.name = "ChatOpenAI"
            mock_grandchild2.run_type = "llm"
            mock_grandchild2.status = "success"
            mock_grandchild2.start_time = datetime(2026, 3, 5, 6, 0, 0, 100000, tzinfo=timezone.utc)
            mock_grandchild2.end_time = datetime(2026, 3, 5, 6, 0, 0, 400000, tzinfo=timezone.utc)
            mock_grandchild2.total_tokens = 500
            mock_grandchild2.total_cost = 0.0005
            mock_grandchild2.extra = {
                "metadata": {},
                "invocation_params": {"model_name": "gpt-4o-mini"}
            }

            mock_root = MagicMock()
            mock_root.id = "root-gc"
            mock_root.trace_id = "root-gc"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 2, tzinfo=timezone.utc)
            mock_root.total_tokens = 812
            mock_root.total_cost = 0.0008

            mock_client = MagicMock()
            # First call: root runs; Second call: ALL descendants (children + grandchildren)
            mock_client.list_runs = MagicMock(
                side_effect=[[mock_root], [mock_child, mock_grandchild, mock_child2, mock_grandchild2]]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    data = response.json()

                    child1 = data["traces"][0]["child_runs"][0]
                    # Model should be extracted from grandchild LLM run via metadata.ls_model_name
                    assert child1["model"] == "groq/llama-3.3-70b"
                    assert child1["name"] == "classify_intent"

                    child2 = data["traces"][0]["child_runs"][1]
                    # Model should be extracted from grandchild LLM run via invocation_params.model_name
                    assert child2["model"] == "gpt-4o-mini"
                    assert child2["name"] == "generate_response"

    def test_traces_child_run_fetch_failure(self):
        """Cover L512-513: child-run fetch exception falls back to empty list."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            mock_root = MagicMock()
            mock_root.id = "root-child-fail"
            mock_root.trace_id = "root-child-fail"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 2, tzinfo=timezone.utc)
            mock_root.total_tokens = 500
            mock_root.total_cost = 0.005

            mock_client = MagicMock()
            # First call returns root runs, second call (descendants fetch) raises
            mock_client.list_runs = MagicMock(
                side_effect=[[mock_root], Exception("Descendant fetch failed")]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["traces"]) == 1
                    # Child runs should be empty due to the exception
                    assert data["traces"][0]["child_runs"] == []
                    assert data["error"] is None

    def test_traces_429_retry_then_success(self):
        """Cover L581-584: 429 rate limit triggers retry with backoff."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            mock_root = MagicMock()
            mock_root.id = "root-retry"
            mock_root.trace_id = "root-retry"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 1, tzinfo=timezone.utc)
            mock_root.total_tokens = 100
            mock_root.total_cost = 0.001

            call_count = 0

            def mock_list_runs(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call (attempt 1 root fetch): raise 429
                    raise Exception("429 Client Error: Too Many Requests")
                elif call_count == 2:
                    # Second call (attempt 2 root fetch): succeed
                    return [mock_root]
                else:
                    # Third call (attempt 2 descendants fetch): succeed
                    return []

            mock_client = MagicMock()
            mock_client.list_runs = MagicMock(side_effect=mock_list_runs)

            with patch("langsmith.Client", return_value=mock_client), \
                 patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["traces"]) == 1
                    assert data["error"] is None
                    # Verify backoff sleep was called once with 5s
                    mock_sleep.assert_called_once_with(5)

    def test_traces_grandchild_orphan_parent(self):
        """Cover L526: LLM grandchild references unknown parent — get_top_level_child returns None."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            # LLM run whose parent is NOT in descendants list
            mock_orphan_llm = MagicMock()
            mock_orphan_llm.id = "orphan-llm"
            mock_orphan_llm.parent_run_id = "unknown-parent-id"  # Not in descendants
            mock_orphan_llm.name = "ChatGroq"
            mock_orphan_llm.run_type = "llm"
            mock_orphan_llm.status = "success"
            mock_orphan_llm.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_orphan_llm.end_time = datetime(2026, 3, 5, 6, 0, 0, 300000, tzinfo=timezone.utc)
            mock_orphan_llm.total_tokens = 100
            mock_orphan_llm.total_cost = 0.0001
            mock_orphan_llm.extra = {"metadata": {"ls_model_name": "groq/llama-3.3-70b"}}

            mock_root = MagicMock()
            mock_root.id = "root-orphan"
            mock_root.trace_id = "root-orphan"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 1, tzinfo=timezone.utc)
            mock_root.total_tokens = 100
            mock_root.total_cost = 0.001

            mock_client = MagicMock()
            # Root runs, then descendants containing only the orphan LLM run
            mock_client.list_runs = MagicMock(
                side_effect=[[mock_root], [mock_orphan_llm]]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["traces"]) == 1
                    # The orphan LLM run should not appear as a child (parent chain broken)
                    assert data["traces"][0]["child_runs"] == []

    def test_traces_grandchild_cycle_detection(self):
        """Cover L530: LLM grandchild parent chain forms a cycle — get_top_level_child returns None."""
        from datetime import datetime, timezone

        with patch.dict(os.environ, {
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "lsv2_pt_test",
            "LANGCHAIN_PROJECT": "aegis",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
            "REDIS_URL": "redis://localhost:6379",
            "FRONTEND_URL": "http://localhost:3000",
        }, clear=False):
            from app.config import get_settings
            get_settings.cache_clear()
            from app.main import _traces_cache
            _traces_cache["data"] = None
            _traces_cache["ts"] = 0.0

            # Two chain runs that reference each other as parents (cycle)
            mock_chain_a = MagicMock()
            mock_chain_a.id = "chain-a"
            mock_chain_a.parent_run_id = "chain-b"  # Points to chain-b
            mock_chain_a.name = "chain_a"
            mock_chain_a.run_type = "chain"
            mock_chain_a.status = "success"
            mock_chain_a.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_chain_a.end_time = datetime(2026, 3, 5, 6, 0, 0, 300000, tzinfo=timezone.utc)
            mock_chain_a.total_tokens = 0
            mock_chain_a.total_cost = 0.0
            mock_chain_a.extra = {"metadata": {}}

            mock_chain_b = MagicMock()
            mock_chain_b.id = "chain-b"
            mock_chain_b.parent_run_id = "chain-a"  # Points back to chain-a (cycle!)
            mock_chain_b.name = "chain_b"
            mock_chain_b.run_type = "chain"
            mock_chain_b.status = "success"
            mock_chain_b.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_chain_b.end_time = datetime(2026, 3, 5, 6, 0, 0, 300000, tzinfo=timezone.utc)
            mock_chain_b.total_tokens = 0
            mock_chain_b.total_cost = 0.0
            mock_chain_b.extra = {"metadata": {}}

            # LLM run under chain-a (its top-level ancestor never reaches root due to cycle)
            mock_llm_cycle = MagicMock()
            mock_llm_cycle.id = "llm-cycle"
            mock_llm_cycle.parent_run_id = "chain-a"  # Parent is chain-a
            mock_llm_cycle.name = "ChatGroq"
            mock_llm_cycle.run_type = "llm"
            mock_llm_cycle.status = "success"
            mock_llm_cycle.start_time = datetime(2026, 3, 5, 6, 0, 0, 100000, tzinfo=timezone.utc)
            mock_llm_cycle.end_time = datetime(2026, 3, 5, 6, 0, 0, 400000, tzinfo=timezone.utc)
            mock_llm_cycle.total_tokens = 200
            mock_llm_cycle.total_cost = 0.0002
            mock_llm_cycle.extra = {"metadata": {"ls_model_name": "groq/llama-3.3-70b"}}

            mock_root = MagicMock()
            mock_root.id = "root-cycle"
            mock_root.trace_id = "root-cycle"
            mock_root.name = "aegis-support-workflow"
            mock_root.status = "success"
            mock_root.start_time = datetime(2026, 3, 5, 6, 0, 0, tzinfo=timezone.utc)
            mock_root.end_time = datetime(2026, 3, 5, 6, 0, 1, tzinfo=timezone.utc)
            mock_root.total_tokens = 200
            mock_root.total_cost = 0.002

            mock_client = MagicMock()
            mock_client.list_runs = MagicMock(
                side_effect=[[mock_root], [mock_chain_a, mock_chain_b, mock_llm_cycle]]
            )

            with patch("langsmith.Client", return_value=mock_client):
                from app.main import app
                with TestClient(app, raise_server_exceptions=False) as c:
                    response = c.get("/api/traces")
                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["traces"]) == 1
                    # Neither chain-a nor chain-b are direct children of root,
                    # and the LLM run's cycle means no model extraction possible
                    # child_runs should be empty since chain-a/b parent isn't root
                    assert data["traces"][0]["child_runs"] == []

