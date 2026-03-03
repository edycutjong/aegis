"""Aegis configuration from environment variables."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    """Application settings loaded from environment."""
    
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_db_url: str = ""
    
    # LLM API Keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    groq_api_key: str = ""
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_seconds: int = 3600  # 1 hour
    
    # Model routing defaults
    fast_model: str = "llama-3.1-8b-instant"
    smart_model: str = "gpt-4o"
    
    # CORS
    frontend_url: str = "http://localhost:3000"
    
    # LangSmith (Observability)
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "aegis"
    
    # App
    debug: bool = False

    def __post_init__(self):
        """Load from environment variables."""
        self.supabase_url = os.getenv("SUPABASE_URL", self.supabase_url)
        self.supabase_key = os.getenv("SUPABASE_KEY", self.supabase_key)
        self.supabase_db_url = os.getenv("SUPABASE_DB_URL", self.supabase_db_url)
        
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
        
        self.debug = os.getenv("DEBUG", "false").lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
