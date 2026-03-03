"""Tests for app.routing.model_router."""

from unittest.mock import patch, MagicMock

from app.routing.model_router import (
    MODEL_PRICING,
    TASK_MODEL_MAP,
    get_model,
    get_cost_per_token,
    calculate_cost,
    _create_model,
)


# ─────────────────────────────────────────────────────────────
# MODEL_PRICING
# ─────────────────────────────────────────────────────────────

class TestModelPricing:
    """Verify pricing dictionary completeness and values."""

    def test_contains_all_expected_models(self):
        expected = {
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
        """Llama-3.1-8b should be the cheapest model by input cost."""
        cheapest = min(MODEL_PRICING.items(), key=lambda x: x[1]["input"])
        assert cheapest[0] == "llama-3.1-8b-instant"


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
        for task in ["classify_intent", "search_docs", "generate_response"]:
            assert TASK_MODEL_MAP[task] == "fast", f"{task} should route to 'fast'"

    def test_smart_tasks(self):
        for task in ["write_sql", "propose_action"]:
            assert TASK_MODEL_MAP[task] == "smart", f"{task} should route to 'smart'"

    def test_covers_all_llm_node_names(self):
        """TASK_MODEL_MAP should cover every agent node that calls an LLM."""
        expected_llm_nodes = {
            "classify_intent",
            "write_sql",
            "search_docs",
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
        mock_create.assert_called_once_with("llama-3.1-8b-instant")

    @patch("app.routing.model_router._create_model")
    def test_smart_task_routes_to_smart_model(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("write_sql")
        mock_create.assert_called_once_with("gpt-4.1")

    @patch("app.routing.model_router._create_model")
    def test_override_model_bypasses_routing(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("classify_intent", override_model="claude-sonnet-4-20250514")
        mock_create.assert_called_once_with("claude-sonnet-4-20250514")

    @patch("app.routing.model_router._create_model")
    def test_unknown_task_defaults_to_fast(self, mock_create, mock_settings):
        mock_create.return_value = MagicMock()
        get_model("some_unknown_task")
        mock_create.assert_called_once_with("llama-3.1-8b-instant")


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
        _create_model("llama-3.1-8b-instant")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "llama-3.1-8b-instant"

    @patch("app.routing.model_router.ChatGroq")
    def test_unknown_prefix_falls_back_to_groq(self, mock_cls, mock_settings):
        _create_model("some-random-model")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "llama-3.1-8b-instant"

    @patch("app.routing.model_router.ChatOpenAI")
    def test_o_prefix_routes_to_openai(self, mock_cls, mock_settings):
        """Models like o1, o3-mini should route to OpenAI."""
        _create_model("o3-mini")
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["model"] == "o3-mini"
