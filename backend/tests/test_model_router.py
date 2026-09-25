"""Tests for app.routing.model_router."""

from unittest.mock import call, patch, MagicMock

import pytest

from app.routing.model_router import (
    FALLBACK_MODEL,
    MODEL_PRICING,
    TASK_MODEL_MAP,
    failover_note,
    get_model,
    primary_model_name,
    get_cost_per_token,
    calculate_cost,
    _create_model,
    provider_of,
    resolved_model_name,
)


# ─────────────────────────────────────────────────────────────
# MODEL_PRICING
# ─────────────────────────────────────────────────────────────

class TestModelPricing:
    """Verify pricing dictionary completeness and values."""

    def test_contains_all_expected_models(self):
        expected = {
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemini-2.5-flash",
            "gemini-2.5-pro-preview-05-06",
            "gpt-4.1",
            "gpt-4.1-mini",
            "claude-sonnet-4-20250514",
            "claude-haiku-4-20250514",
        }
        assert set(MODEL_PRICING.keys()) == expected

    def test_all_entries_have_input_and_output(self):
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing, f"{model} missing 'input'"
            assert "output" in pricing, f"{model} missing 'output'"
            assert pricing["input"] >= 0, f"{model} has negative input price"
            assert pricing["output"] >= 0, f"{model} has negative output price"

    def test_groq_is_cheapest(self):
        """The fast Groq model should be the cheapest by input cost."""
        cheapest = min(MODEL_PRICING.items(), key=lambda x: x[1]["input"])
        assert cheapest[0] == "llama-3.1-8b-instant"  # retired, kept for historical pricing


# ─────────────────────────────────────────────────────────────
# get_cost_per_token
# ─────────────────────────────────────────────────────────────

class TestGetCostPerToken:
    def test_known_model(self):
        result = get_cost_per_token("gpt-4.1")
        assert result == {"input": 2.00, "output": 8.00}

    def test_unknown_model_returns_zeros(self):
        result = get_cost_per_token("nonexistent-model")
        assert result == {"input": 0.0, "output": 0.0}


# ─────────────────────────────────────────────────────────────
# calculate_cost
# ─────────────────────────────────────────────────────────────

class TestCalculateCost:
    def test_zero_tokens(self):
        cost = calculate_cost("gpt-4.1", 0, 0)
        assert cost == 0.0

    def test_typical_usage(self):
        # gpt-4.1: input $2.00/1M, output $8.00/1M
        # 1000 prompt + 500 completion
        cost = calculate_cost("gpt-4.1", 1000, 500)
        expected = (1000 / 1_000_000) * 2.00 + (500 / 1_000_000) * 8.00
        assert cost == round(expected, 6)

    def test_million_tokens(self):
        cost = calculate_cost("llama-3.1-8b-instant", 1_000_000, 1_000_000)
        expected = 0.05 + 0.08
        assert cost == round(expected, 6)

    def test_unknown_model_zero_cost(self):
        cost = calculate_cost("unknown-model", 1000, 1000)
        assert cost == 0.0


# ─────────────────────────────────────────────────────────────
# TASK_MODEL_MAP
# ─────────────────────────────────────────────────────────────

class TestTaskModelMap:
    def test_fast_tasks(self):
        for task in ["classify_intent", "propose_action", "generate_response"]:
            assert TASK_MODEL_MAP[task] == "fast", f"{task} should route to 'fast'"

    def test_smart_tasks(self):
        for task in ["write_sql"]:
            assert TASK_MODEL_MAP[task] == "smart", f"{task} should route to 'smart'"

    def test_covers_all_llm_node_names(self):
        """TASK_MODEL_MAP should cover every agent node that calls an LLM."""
        expected_llm_nodes = {
            "classify_intent",
            "write_sql",
            "propose_action",
            "generate_response",
        }
        assert expected_llm_nodes == set(TASK_MODEL_MAP.keys())


# ─────────────────────────────────────────────────────────────
# get_model
# ─────────────────────────────────────────────────────────────

class TestGetModel:
    @patch("app.routing.model_router._create_model")
    def test_fast_task_routes_to_fast_model(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("classify_intent")
        assert mock_create.call_args_list[0] == call("gpt-4.1-mini", max_retries=0)

    @patch("app.routing.model_router._create_model")
    def test_smart_task_routes_to_smart_model(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("write_sql")
        assert mock_create.call_args_list[0] == call("gpt-4.1", max_retries=0)

    @patch("app.routing.model_router._create_model")
    def test_override_model_bypasses_routing(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("classify_intent", override_model="claude-sonnet-4-20250514")
        assert mock_create.call_args_list[0] == call("claude-sonnet-4-20250514", max_retries=0)

    @patch("app.routing.model_router._create_model")
    def test_unknown_task_defaults_to_fast(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("some_unknown_task")
        assert mock_create.call_args_list[0] == call("gpt-4.1-mini", max_retries=0)


# ─────────────────────────────────────────────────────────────
# _create_model
# ─────────────────────────────────────────────────────────────

class TestCreateModel:
    @patch("app.routing.model_router.ChatGoogleGenerativeAI")
    def test_gemini_prefix(self, mock_cls, mock_settings):
        _create_model("gemini-2.5-flash")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "gemini-2.5-flash"

    @patch("app.routing.model_router.ChatOpenAI")
    def test_gpt_prefix(self, mock_cls, mock_settings):
        _create_model("gpt-4.1")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "gpt-4.1"

    @patch("app.routing.model_router.ChatAnthropic")
    def test_claude_prefix(self, mock_cls, mock_settings):
        _create_model("claude-sonnet-4-20250514")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "claude-sonnet-4-20250514"

    @patch("app.routing.model_router.ChatGroq")
    def test_llama_prefix(self, mock_cls, mock_settings):
        """Legacy bare llama-* ids still pass through to Groq unchanged."""
        _create_model("llama-3.1-8b-instant")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "llama-3.1-8b-instant"

    @patch("app.routing.model_router.ChatGroq")
    def test_unknown_prefix_falls_back_to_groq(self, mock_cls, mock_settings):
        _create_model("some-random-model")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "openai/gpt-oss-20b"

    @patch("app.routing.model_router.ChatGroq")
    def test_openai_namespaced_model_routes_to_groq_not_openai(self, mock_cls, mock_settings):
        """Regression: "openai/gpt-oss-20b".startswith("o") is True.

        Before the namespace check was moved ahead of the OpenAI branch, every
        Groq-hosted `openai/*` model was constructed as a ChatOpenAI client with
        the OpenAI key, which 404s. Pins the branch order.
        """
        _create_model("openai/gpt-oss-20b")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "openai/gpt-oss-20b"

    @patch("app.routing.model_router.ChatOpenAI")
    def test_o_prefix_routes_to_openai(self, mock_cls, mock_settings):
        """Models like o1, o3-mini should route to OpenAI."""
        _create_model("o3-mini")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "o3-mini"


# ─────────────────────────────────────────────────────────────
# Primary models and the failover note
# ─────────────────────────────────────────────────────────────

class TestPrimaryAndFailoverNote:
    @pytest.mark.parametrize("task,model", [
        ("classify_intent", "gpt-4.1-mini"), ("propose_action", "gpt-4.1-mini"),
        ("generate_response", "gpt-4.1-mini"), ("write_sql", "gpt-4.1"), ("unknown", "gpt-4.1-mini"),
    ])
    def test_primary_model_name(self, task, model, mock_settings):
        assert primary_model_name(task) == model

    @patch("app.routing.model_router._create_model")
    def test_chat_steps_run_on_openai_with_a_groq_backup(self, mock_create, mock_settings):
        primary, fallback = MagicMock(), MagicMock()
        mock_create.side_effect = [primary, fallback]
        result = get_model("propose_action")
        assert mock_create.call_args_list == [call("gpt-4.1-mini", max_retries=0), call("openai/gpt-oss-120b")]
        primary.with_fallbacks.assert_called_once_with([fallback])
        assert result is primary.with_fallbacks.return_value

    @pytest.mark.parametrize("answered,noted", [
        ("gpt-4.1-mini", False),
        ("gpt-4.1-mini-2025-04-14", False),
        ("openai/gpt-oss-120b", True),
        ("gpt-4.1-mini-preview", True),
    ])
    def test_note_only_when_a_backup_answered(self, answered, noted, mock_settings):
        response = MagicMock(response_metadata={"model_name": answered})
        note = failover_note("generate_response", "Resolution", None, response)
        assert bool(note) is noted
        if noted:
            assert note == [f"↪ [Resolution] gpt-4.1-mini unavailable, answered by backup {answered}"]

    def test_bigger_model_never_passes_for_its_mini_sibling(self, mock_settings):
        """gpt-4.1-mini answering for gpt-4.1 is a failover, not a match."""
        response = MagicMock(response_metadata={"model_name": "gpt-4.1-mini-2025-04-14"})
        assert failover_note("write_sql", "Investigator", None, response)

    def test_unknown_model_adds_no_note(self, mock_settings):
        assert failover_note("write_sql", "Investigator", None, object()) == []


# ─────────────────────────────────────────────────────────────
# Failover, attribution, pricing
# ─────────────────────────────────────────────────────────────

class TestFailover:
    @pytest.mark.parametrize("model,provider", [
        ("openai/gpt-oss-120b", "groq"), ("llama-3.1-8b-instant", "groq"),
        ("gemini-2.5-flash", "google"), ("gpt-4.1", "openai"), ("o3-mini", "openai"),
        ("claude-sonnet-4-20250514", "anthropic"), ("mystery", "groq"),
    ])
    def test_provider_of(self, model, provider):
        assert provider_of(model) == provider

    def test_every_fallback_is_a_different_provider(self):
        for provider, fallback in FALLBACK_MODEL.items():
            assert provider_of(fallback) != provider

    @pytest.mark.asyncio
    async def test_throttled_primary_actually_fails_over(self, mock_settings):
        """End-to-end through LangChain's real fallback runnable."""
        from langchain_core.runnables import RunnableLambda

        def throttled(_):
            raise RuntimeError("429 rate limit")

        with patch("app.routing.model_router._create_model") as mock_create:
            primary = RunnableLambda(throttled)
            mock_create.side_effect = [primary, RunnableLambda(lambda _: "answered by fallback")]
            llm = get_model("propose_action")
        assert await llm.ainvoke("hi") == "answered by fallback"


class TestResolvedModelName:
    def test_prefers_response_metadata(self):
        response = MagicMock(response_metadata={"model_name": "gpt-4.1-mini-2025-04-14"})
        assert resolved_model_name(MagicMock(model_name="configured"), response) == "gpt-4.1-mini-2025-04-14"

    def test_strips_gemini_models_prefix(self):
        response = MagicMock(response_metadata={"model": "models/gemini-2.5-flash"})
        assert resolved_model_name(None, response) == "gemini-2.5-flash"

    def test_falls_back_to_llm_attributes(self):
        response = MagicMock(response_metadata={})
        assert resolved_model_name(MagicMock(model_name="gpt-4.1"), response) == "gpt-4.1"

        class OnlyModel:
            model = "models/gemini-2.5-flash"
        assert resolved_model_name(OnlyModel(), object()) == "gemini-2.5-flash"

    def test_unknown_when_nothing_identifies_the_model(self):
        assert resolved_model_name(object(), object()) == "unknown"


def test_dated_snapshot_ids_are_priced_by_prefix():
    assert get_cost_per_token("gpt-4.1-mini-2025-04-14") == MODEL_PRICING["gpt-4.1-mini"]
    assert get_cost_per_token("gpt-4.1-2025-04-14") == MODEL_PRICING["gpt-4.1"]
    assert get_cost_per_token("models/gemini-2.5-flash") == MODEL_PRICING["gemini-2.5-flash"]


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "gemini-2.5-flash", "gpt-4.1", "claude-sonnet-4-20250514"])
def test_every_client_has_a_request_timeout(model, mock_settings):
    """A hung provider must time out (and fail over), not hang the workflow."""
    from app.routing.model_router import REQUEST_TIMEOUT_S
    llm = _create_model(model)
    timeouts = [getattr(llm, a, None) for a in ("request_timeout", "timeout", "default_request_timeout")]
    assert REQUEST_TIMEOUT_S in timeouts
