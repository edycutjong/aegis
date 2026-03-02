"""Shared test fixtures for the Aegis backend."""

import os
import pytest
from unittest.mock import patch

from app.config import Settings, get_settings


@pytest.fixture
def mock_settings():
    """Return a Settings instance with dummy values (no real API keys)."""
    with patch.dict(os.environ, {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_KEY": "test-anon-key",
        "SUPABASE_DB_URL": "postgresql://test:test@localhost/test",
        "OPENAI_API_KEY": "sk-test-openai",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "GOOGLE_API_KEY": "AIza-test",
        "GROQ_API_KEY": "gsk_test-groq",
        "REDIS_URL": "redis://localhost:6379",
        "FAST_MODEL": "llama-3.1-8b-instant",
        "SMART_MODEL": "gpt-4.1",
        "FRONTEND_URL": "http://localhost:3000",
        "DEBUG": "false",
    }, clear=False):
        get_settings.cache_clear()
        settings = get_settings()
        yield settings
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all module-level singletons between tests."""
    yield

    # Clear get_settings LRU cache
    get_settings.cache_clear()

    # Reset cache singleton
    import app.cache.semantic as cache_mod
    cache_mod._cache = None

    # Reset db singleton
    import app.db.supabase as db_mod
    db_mod._client = None

    # Reset tracker singleton
    import app.observability.tracker as tracker_mod
    tracker_mod._tracker = None
