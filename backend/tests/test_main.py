"""Tests for app.main — FastAPI endpoints with mocked dependencies."""

import os
import pytest
from unittest.mock import patch, AsyncMock

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
        # Cleanup
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
