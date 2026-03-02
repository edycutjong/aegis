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
            assert s.fast_model == "llama-3.1-8b-instant"

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


class TestGetSettingsCaching:
    """get_settings() should be a cached singleton."""

    def test_returns_same_instance(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
