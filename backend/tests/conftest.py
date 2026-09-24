"""Shared test fixtures for the Aegis backend."""

import os

# Tests must never send traces anywhere. app.config loads backend/.env, which
# enables LangSmith for the running app; without this every test run would
# upload spans to the real project (and burn its monthly trace quota).
# Set before any app import so load_dotenv (override=False) cannot flip it.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
import pytest
from unittest.mock import patch

from app.config import get_settings


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
        "FAST_MODEL": "openai/gpt-oss-20b",
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

    # Reset the demo rate limiter so request counts never leak between tests
    import sys
    main_mod = sys.modules.get("app.main")
    if main_mod is not None:
        main_mod.rate_limiter._hits.clear()
        main_mod.rate_limiter._day_count = 0
