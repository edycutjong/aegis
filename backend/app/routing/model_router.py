"""Dynamic model routing for cost optimization.

Classification runs on a fast model and SQL generation on the frontier model
(GPT-4.1), since a wrong query is the expensive mistake. Action proposal and
the reply use the intent lane chosen by the classifier: gpt-oss-120b on Groq
for billing and general, Gemini 2.5 Flash for technical and account. The
amount cap, identity override and approval gate are enforced in code after
the model answers, whichever model that was.
"""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from pydantic import SecretStr

from app.config import get_settings

# Model pricing per 1M tokens (input/output)
# Groq rates verified against console.groq.com/docs/model/<id> on 2026-08-18.
MODEL_PRICING = {
    # Groq (open-weight models)
    # NOTE: gpt-oss are reasoning models — reasoning tokens are billed as
    # completion tokens, so real output cost per call runs higher than a
    # non-reasoning model at the same headline rate.
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
    # Retired by Groq (2026) — kept so historical tracker data still prices.
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    # Google
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro-preview-05-06": {"input": 1.25, "output": 10.00},
    # OpenAI
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-20250514": {"input": 0.80, "output": 4.00},
}

# Task → Model complexity mapping
TASK_MODEL_MAP = {
    "classify_intent": "fast",      # Classification → FAST_MODEL (Groq gpt-oss-20b)
    "write_sql": "smart",           # SQL generation → SMART_MODEL (GPT-4.1)
    "search_docs": "fast",          # (retrieval is deterministic; kept for completeness)
    "propose_action": "smart",      # Default when no intent lane is set → SMART_MODEL
    "generate_response": "fast",    # Default when no intent lane is set → FAST_MODEL
}

# Intent → Model provider routing (set by classifier)
INTENT_MODEL_MAP = {
    "groq": "openai/gpt-oss-120b",   # Simple intents (billing, general)
    "gemini": "gemini-2.5-flash",     # Complex intents (technical, account)
}


# A hung provider must not hang the workflow: each call gives up after this,
# which also triggers the cross-provider fallback below.
REQUEST_TIMEOUT_S = 30.0

# Cross-provider failover. Evals showed both free-tier providers throttle under
# modest concurrency (Gemini: 5 req/min; Groq gpt-oss-120b: 8K tokens/min), and
# the old "fallback" pointed at the same provider that had just failed. Each
# primary now fails fast (no retry sleep) and hands off to a different vendor.
FALLBACK_MODEL = {
    "groq": "gpt-4.1-mini",
    "google": "gpt-4.1-mini",
    "openai": "gemini-2.5-flash",
    "anthropic": "gpt-4.1-mini",
}


def provider_of(model_name: str) -> str:
    """Which vendor serves a model id (mirrors the dispatch in _create_model)."""
    if "/" in model_name or model_name.startswith("llama"):
        return "groq"
    if model_name.startswith("gemini"):
        return "google"
    if model_name.startswith("gpt") or model_name.startswith("o"):
        return "openai"
    if model_name.startswith("claude"):
        return "anthropic"
    return "groq"


def _with_fallback(model_name: str):
    """Primary model that fails fast, wrapped with a different-provider fallback."""
    primary = _create_model(model_name, max_retries=0)
    fallback = _create_model(FALLBACK_MODEL[provider_of(model_name)])
    return primary.with_fallbacks([fallback])


def resolved_model_name(llm, response) -> str:
    """Name of the model that actually answered — after any failover.

    Prefer the provider's own response metadata; a fallback wrapper has no
    `model_name`, and the configured name would misattribute failed-over cost.
    """
    meta = getattr(response, "response_metadata", None)
    if isinstance(meta, dict):
        name = meta.get("model_name") or meta.get("model")
        if isinstance(name, str) and name:
            return name.removeprefix("models/")
    for attr in ("model_name", "model"):
        value = getattr(llm, attr, None)
        if isinstance(value, str) and value:
            return value.removeprefix("models/")
    return "unknown"


def get_model(task: str, override_model: str | None = None):
    """Get the appropriate LLM for a given task.

    Args:
        task: The agent task name (e.g., 'classify_intent', 'write_sql')
        override_model: Optional specific model to use

    Returns:
        A LangChain chat model instance
    """
    settings = get_settings()

    if override_model:
        model_name = override_model
    else:
        complexity = TASK_MODEL_MAP.get(task, "fast")
        model_name = settings.smart_model if complexity == "smart" else settings.fast_model

    return _with_fallback(model_name)


def get_model_for_intent(task: str, model_provider: str | None = None):
    """Get the appropriate LLM for a task, routed by intent classification.

    For tasks like 'propose_action' and 'generate_response', uses the
    model_provider set by the classifier (groq for simple intents,
    gemini for complex). Each primary fails over to a different vendor
    (see FALLBACK_MODEL).

    Args:
        task: The agent task name
        model_provider: 'groq' or 'gemini', set by classify_intent
    """
    # Only route downstream agents; classification/SQL keep their defaults
    routable_tasks = {"propose_action", "generate_response"}

    if model_provider and task in routable_tasks:
        model_name = INTENT_MODEL_MAP.get(model_provider)
        if model_name:
            return _with_fallback(model_name)

    # Default: use standard task→model routing
    return get_model(task)


def _create_model(model_name: str, max_retries: int = 2):
    """Create a LangChain model instance by name."""
    settings = get_settings()

    # Groq's catalogue is namespaced (openai/…, qwen/…, groq/…) plus the legacy
    # bare llama-* ids. This branch MUST come before the OpenAI check: it also
    # matches startswith("o"), which would otherwise route "openai/gpt-oss-20b"
    # to ChatOpenAI with the wrong API key.
    if "/" in model_name or model_name.startswith("llama"):
        return ChatGroq(
            model=model_name,
            api_key=SecretStr(settings.groq_api_key),
            temperature=0.1,
            max_retries=max_retries,
            timeout=REQUEST_TIMEOUT_S,
        )
    elif model_name.startswith("gemini"):
        return ChatGoogleGenerativeAI(  # type: ignore[call-arg]  # pydantic alias
            model=model_name,
            google_api_key=SecretStr(settings.google_api_key),
            temperature=0.1,
            max_retries=max_retries,
            timeout=REQUEST_TIMEOUT_S,
        )
    elif model_name.startswith("gpt") or model_name.startswith("o"):
        return ChatOpenAI(
            model=model_name,
            api_key=SecretStr(settings.openai_api_key),
            temperature=0.1,
            max_retries=max_retries,
            timeout=REQUEST_TIMEOUT_S,
        )
    elif model_name.startswith("claude"):
        return ChatAnthropic(  # type: ignore[call-arg]  # `model` is a pydantic alias of model_name
            model=model_name,
            api_key=SecretStr(settings.anthropic_api_key),
            temperature=0.1,
            max_retries=max_retries,
            timeout=REQUEST_TIMEOUT_S,
        )
    else:
        # Default to the cheapest Groq option
        return ChatGroq(
            model="openai/gpt-oss-20b",
            api_key=SecretStr(settings.groq_api_key),
            temperature=0.1,
            max_retries=max_retries,
            timeout=REQUEST_TIMEOUT_S,
        )


def get_cost_per_token(model_name: str) -> dict:
    """Get pricing for a specific model.

    Providers report dated snapshots ("gpt-4.1-mini-2025-04-14"), so fall back
    to the longest configured id that the reported name starts with.
    """
    name = model_name.removeprefix("models/")
    if name in MODEL_PRICING:
        return MODEL_PRICING[name]
    for known in sorted(MODEL_PRICING, key=len, reverse=True):
        if name.startswith(known):
            return MODEL_PRICING[known]
    return {"input": 0.0, "output": 0.0}


def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate USD cost for a specific LLM call."""
    pricing = get_cost_per_token(model_name)
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 6)
