"""Model routing.

SQL generation runs on the frontier model (SMART_MODEL, GPT-4.1), since a
wrong query is the expensive mistake. Classification, action proposal and the
reply run on FAST_MODEL (gpt-4.1-mini). Each primary fails over to a model
from a different vendor, and `failover_note` puts that on the trace, so the
log never names a model that didn't answer.

Groq's free tier used to serve the chat steps, but it throttled under eval
load and most calls failed over: the scorecards were measuring the backup.
Groq now serves only Llama Prompt Guard 2 (app/agent/screen.py) and the
backup for OpenAI. The amount cap, identity override and approval gate are
enforced in code after the model answers, whichever model that was.
"""

import re

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
    "classify_intent": "fast",      # FAST_MODEL (gpt-4.1-mini)
    "write_sql": "smart",           # SMART_MODEL (GPT-4.1)
    "propose_action": "fast",       # FAST_MODEL; the invariants hold whatever it proposes
    "generate_response": "fast",    # FAST_MODEL
}


# A hung provider must not hang the workflow: each call gives up after this,
# which also triggers the cross-provider fallback below.
REQUEST_TIMEOUT_S = 30.0

# Cross-provider failover: each primary fails fast (no retry sleep) and hands
# off to a different vendor, so one provider's outage or throttling can't
# stop a run. Groq is the OpenAI backup: free-tier limits make it a poor
# primary but a usable second chance.
FALLBACK_MODEL = {
    "groq": "gpt-4.1-mini",
    "google": "gpt-4.1-mini",
    "openai": "openai/gpt-oss-120b",
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


def primary_model_name(task: str) -> str:
    """The configured primary for a task (before any failover)."""
    settings = get_settings()
    return settings.smart_model if TASK_MODEL_MAP.get(task, "fast") == "smart" else settings.fast_model


def get_model(task: str, override_model: str | None = None):
    """The task's primary model, wrapped with a different-vendor fallback."""
    return _with_fallback(override_model or primary_model_name(task))


def failover_note(task: str, agent: str, llm, response) -> list[str]:
    """A trace line when a backup answered instead of the task's primary.

    Providers report dated snapshots (gpt-4.1-mini-2025-04-14), so the primary
    matches with or without a date suffix, but gpt-4.1-mini never passes for
    gpt-4.1.
    """
    primary = primary_model_name(task)
    answered = resolved_model_name(llm, response)
    if answered == "unknown" or re.fullmatch(rf"{re.escape(primary)}(-\d{{4}}-\d{{2}}-\d{{2}})?", answered):
        return []
    return [f"↪ [{agent}] {primary} unavailable, answered by backup {answered}"]


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
