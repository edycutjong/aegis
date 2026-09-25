"""Aegis configuration from environment variables."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # Load .env file for local (non-Docker) runs


@dataclass
class Settings:
    """Application settings loaded from environment."""

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # LLM API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600  # 1 hour

    # Model routing defaults
    fast_model: str = "gpt-4.1-mini"
    smart_model: str = "gpt-4.1"

    # CORS
    frontend_url: str = "http://localhost:3000"

    # LangSmith (Observability)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "aegis"

    # Public-demo spend protection (see app/ratelimit.py)
    rate_limit_per_client: int = 8
    rate_limit_window_seconds: int = 600
    daily_ticket_cap: int = 300
    max_message_chars: int = 1000

    def __post_init__(self):
        """Load from environment variables."""
        self.supabase_url = os.getenv("SUPABASE_URL", self.supabase_url)
        self.supabase_key = os.getenv("SUPABASE_KEY", self.supabase_key)

        self.openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key)
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", self.anthropic_api_key)
        self.google_api_key = os.getenv("GOOGLE_API_KEY", self.google_api_key)
        self.groq_api_key = os.getenv("GROQ_API_KEY", self.groq_api_key)

        self.redis_url = os.getenv("REDIS_URL", self.redis_url)
        self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", self.cache_ttl_seconds))

        self.fast_model = os.getenv("FAST_MODEL", self.fast_model)
        self.smart_model = os.getenv("SMART_MODEL", self.smart_model)

        self.frontend_url = os.getenv("FRONTEND_URL", self.frontend_url)

        self.langchain_tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        self.langchain_api_key = os.getenv("LANGCHAIN_API_KEY", self.langchain_api_key)
        self.langchain_project = os.getenv("LANGCHAIN_PROJECT", self.langchain_project)

        self.rate_limit_per_client = int(os.getenv("RATE_LIMIT_PER_CLIENT", self.rate_limit_per_client))
        self.rate_limit_window_seconds = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", self.rate_limit_window_seconds))
        self.daily_ticket_cap = int(os.getenv("DAILY_TICKET_CAP", self.daily_ticket_cap))
        self.max_message_chars = int(os.getenv("MAX_MESSAGE_CHARS", self.max_message_chars))

    @property
    def cors_origins(self) -> list[str]:
        """FRONTEND_URL may be a comma-separated list (e.g. prod + custom domain)."""
        return [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
