"""Tests for app.main — FastAPI endpoints with mocked dependencies."""

import asyncio
import json
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock

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
        del thread_store["approval-test"]

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
