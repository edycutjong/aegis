"""Tests for app.config."""

import os
from unittest.mock import patch

from app.config import Settings, get_settings


class TestSettingsDefaults:
    """Settings should have sensible defaults when no env vars are set."""

    def test_default_fast_model(self):
        with patch.dict(os.environ, {}, clear=True):
            get_settings.cache_clear()
            s = Settings()
            assert s.fast_model == "openai/gpt-oss-20b"

    def test_default_smart_model(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.smart_model == "gpt-4o"

    def test_default_redis_url(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.redis_url == "redis://localhost:6379"

    def test_default_debug_is_false(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.debug is False


class TestSettingsFromEnv:
    """Settings.__post_init__ should read from environment variables."""

    def test_groq_api_key_from_env(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_my_key"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.groq_api_key == "gsk_my_key"

    def test_fast_model_from_env(self):
        with patch.dict(os.environ, {"FAST_MODEL": "gemini-2.5-flash"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.fast_model == "gemini-2.5-flash"

    def test_debug_true_from_env(self):
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.debug is True

    def test_debug_case_insensitive(self):
        with patch.dict(os.environ, {"DEBUG": "TRUE"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.debug is True


class TestSettingsAllEnvFields:
    """Every remaining Settings field should map from its env var (L48-63)."""

    def test_supabase_url_from_env(self):
        with patch.dict(os.environ, {"SUPABASE_URL": "https://proj.supabase.co"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.supabase_url == "https://proj.supabase.co"

    def test_supabase_key_from_env(self):
        with patch.dict(os.environ, {"SUPABASE_KEY": "anon-key-123"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.supabase_key == "anon-key-123"

    def test_supabase_db_url_from_env(self):
        with patch.dict(os.environ, {"SUPABASE_DB_URL": "postgresql://u:p@host/db"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.supabase_db_url == "postgresql://u:p@host/db"

    def test_openai_api_key_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.openai_api_key == "sk-openai-test"

    def test_anthropic_api_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.anthropic_api_key == "sk-ant-test"

    def test_google_api_key_from_env(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "AIza-test"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.google_api_key == "AIza-test"

    def test_redis_url_from_env(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://cache-host:6380"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.redis_url == "redis://cache-host:6380"

    def test_cache_ttl_seconds_from_env(self):
        with patch.dict(os.environ, {"CACHE_TTL_SECONDS": "7200"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.cache_ttl_seconds == 7200

    def test_smart_model_from_env(self):
        with patch.dict(os.environ, {"SMART_MODEL": "claude-sonnet-4-20250514"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.smart_model == "claude-sonnet-4-20250514"

    def test_frontend_url_from_env(self):
        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.example.com"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.frontend_url == "https://app.example.com"


class TestGetSettingsCaching:
    """get_settings() should be a cached singleton."""

    def test_returns_same_instance(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2


class TestLangSmithSettings:
    """LangSmith observability settings."""

    def test_default_tracing_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.langchain_tracing_v2 is False

    def test_default_project_name(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.langchain_project == "aegis"

    def test_default_api_key_empty(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            assert s.langchain_api_key == ""

    def test_tracing_enabled_from_env(self):
        with patch.dict(os.environ, {"LANGCHAIN_TRACING_V2": "true"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.langchain_tracing_v2 is True

    def test_api_key_from_env(self):
        with patch.dict(os.environ, {"LANGCHAIN_API_KEY": "lsv2_pt_test"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.langchain_api_key == "lsv2_pt_test"

    def test_project_from_env(self):
        with patch.dict(os.environ, {"LANGCHAIN_PROJECT": "my-project"}, clear=False):
            get_settings.cache_clear()
            s = Settings()
            assert s.langchain_project == "my-project"
