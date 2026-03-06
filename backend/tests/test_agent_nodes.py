"""Tests for pure-logic functions in app.agent.nodes."""

import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.nodes import (
    should_retry_sql,
    should_execute,
    _extract_customer_info,
    _fuzzy_name_match,
    _status_warning,
    _search_customers_by_name,
    should_proceed_after_validation,
    validate_customer,
    classify_intent,
    write_sql,
    execute_sql,
    search_docs,
    propose_action,
    execute_action,
    generate_response,
    await_approval,
)


class TestShouldRetrySql:
    """Conditional edge: retry SQL on error (up to 3 attempts), 0-records guard."""

    def test_retries_when_error_and_under_limit(self):
        state = {"sql_error": "relation does not exist", "sql_retry_count": 1}
        assert should_retry_sql(state) == "write_sql"

    def test_stops_retrying_at_limit(self):
        state = {"sql_error": "syntax error", "sql_retry_count": 3}
        assert should_retry_sql(state) == "search_docs"

    def test_proceeds_when_has_data(self):
        state = {"sql_error": "", "sql_retry_count": 0, "sql_result": [{"id": 1}]}
        assert should_retry_sql(state) == "search_docs"

    def test_zero_records_short_circuits(self):
        state = {"sql_error": "", "sql_retry_count": 0, "sql_result": []}
        assert should_retry_sql(state) == "generate_response"

    def test_proceeds_when_error_is_none(self):
        state = {}
        assert should_retry_sql(state) == "generate_response"  # No data = 0 records


class TestShouldExecute:
    """Conditional edge: execute approved actions, skip denied."""

    def test_approved_routes_to_execute(self):
        state = {"approval_status": "approved"}
        assert should_execute(state) == "execute_action"

    def test_denied_routes_to_response(self):
        state = {"approval_status": "denied"}
        assert should_execute(state) == "generate_response"

    def test_pending_routes_to_response(self):
        state = {"approval_status": "pending"}
        assert should_execute(state) == "generate_response"

    def test_missing_status_routes_to_response(self):
        state = {}
        assert should_execute(state) == "generate_response"


# ─────────────────────────────────────────────────────────────
# Customer Validation Tests
# ─────────────────────────────────────────────────────────────


class TestExtractCustomerInfo:
    """Parse customer ID and name from ticket messages."""

    def test_id_and_name(self):
        cid, name = _extract_customer_info("Customer #8 David Martinez was charged twice")
        assert cid == 8
        assert name == "David Martinez"

    def test_id_only(self):
        cid, name = _extract_customer_info("Customer #42 has an issue")
        assert cid == 42
        assert name is None

    def test_name_only_with_keyword(self):
        cid, name = _extract_customer_info("Emily Davis reports a billing issue")
        assert cid is None
        # name might be None since "Emily Davis" follows no keyword like "Customer"
        # but should work with "for Emily Davis"

    def test_name_only_for_keyword(self):
        cid, name = _extract_customer_info("Refund requested for Emily Davis")
        assert cid is None
        assert name == "Emily Davis"

    def test_no_customer_info(self):
        cid, name = _extract_customer_info("Server is slow")
        assert cid is None
        assert name is None

    def test_customer_no_hash(self):
        cid, name = _extract_customer_info("customer 5 needs help")
        assert cid == 5


class TestFuzzyNameMatch:
    """Fuzzy name matching for typo detection."""

    def test_exact_match(self):
        assert _fuzzy_name_match("David Martinez", "David Martinez") == 1.0

    def test_case_insensitive(self):
        assert _fuzzy_name_match("david martinez", "David Martinez") == 1.0

    def test_typo_high_similarity(self):
        score = _fuzzy_name_match("Davd Martines", "David Martinez")
        assert score >= 0.75  # Should pass fuzzy threshold

    def test_completely_different(self):
        score = _fuzzy_name_match("Sarah Chen", "David Martinez")
        assert score < 0.5


class TestShouldProceedAfterValidation:
    """Conditional edge after customer validation."""

    def test_customer_found(self):
        assert should_proceed_after_validation({"customer_found": True}) == "write_sql"

    def test_customer_not_found(self):
        assert should_proceed_after_validation({"customer_found": False}) == "generate_response"

    def test_missing_defaults_to_proceed(self):
        assert should_proceed_after_validation({}) == "write_sql"


class TestStatusWarning:
    """Status warnings for suspended/cancelled customers."""

    def test_active_no_warning(self):
        assert _status_warning({"id": 1, "name": "Test", "status": "active"}) is None

    def test_suspended_warning(self):
        warning = _status_warning({"id": 5, "name": "Emily Davis", "status": "suspended"})
        assert warning is not None
        assert "SUSPENDED" in warning

    def test_cancelled_warning(self):
        warning = _status_warning({"id": 3, "name": "Test User", "status": "cancelled"})
        assert warning is not None
        assert "CANCELLED" in warning


# ─────────────────────────────────────────────────────────────
# Async Integration Tests — validate_customer (mocked DB)
# ─────────────────────────────────────────────────────────────



def _make_state(msg: str) -> dict:
    """Create a minimal AgentState dict for testing."""
    return {"user_message": msg, "thought_log": []}


def _mock_db_with_customer(customer: dict | None):
    """Return a mock SupabaseClient whose execute_sql returns the given customer."""
    mock_db = MagicMock()
    if customer:
        mock_db.execute_sql = AsyncMock(return_value={"success": True, "data": [customer]})
    else:
        mock_db.execute_sql = AsyncMock(return_value={"success": True, "data": []})
    return mock_db


DAVID = {"id": 8, "name": "David Martinez", "email": "david@example.com", "plan": "pro", "status": "active"}
EMILY = {"id": 5, "name": "Emily Davis", "email": "emily@example.com", "plan": "enterprise", "status": "suspended"}


class TestValidateCustomerAsync:
    """Full async tests for validate_customer with mocked Supabase."""

    @pytest.mark.asyncio
    async def test_case1_id_and_name_match(self):
        """Case 1: ID + Name match → customer_found=True."""
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 David Martinez was charged twice"))
        assert result["customer_found"] is True
        assert any("validated" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case2_id_and_name_mismatch(self):
        """Case 2: ID exists + wrong name → customer_found=False."""
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 Sarah Chen was charged twice"))
        assert result["customer_found"] is False
        assert "David Martinez" in result["final_response"]
        assert "Sarah Chen" in result["final_response"]

    @pytest.mark.asyncio
    async def test_case3_fuzzy_typo(self):
        """Case 3: ID + typo name → auto-correct, customer_found=True."""
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 Davd Martines was charged twice"))
        assert result["customer_found"] is True
        assert any("typo" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case4_id_only(self):
        """Case 4: ID only, no name → customer_found=True."""
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 has been charged twice"))
        assert result["customer_found"] is True

    @pytest.mark.asyncio
    async def test_case5_name_only_single_match(self):
        """Case 5: No ID + name → single match found, customer_found=True."""
        mock_db = _mock_db_with_customer(None)  # No ID lookup needed
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db), \
             patch("app.agent.agents.investigator._search_customers_by_name", new_callable=AsyncMock, return_value=[EMILY]):
            result = await validate_customer(_make_state("Refund requested for Emily Davis"))
        assert result["customer_found"] is True
        assert any("found by name" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case5_name_only_multiple_matches(self):
        """Case 5: No ID + name → multiple matches, returns candidates for disambiguation."""
        emily2 = {"id": 15, "name": "Emily Davidson", "email": "e2@example.com", "plan": "basic", "status": "active"}
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(None)), \
             patch("app.agent.agents.investigator._search_customers_by_name", new_callable=AsyncMock, return_value=[EMILY, emily2]):
            result = await validate_customer(_make_state("Refund requested for Emily Davis"))
        assert result["customer_found"] is False
        assert "customer_candidates" in result
        assert len(result["customer_candidates"]) == 2

    @pytest.mark.asyncio
    async def test_case6_no_id_no_name(self):
        """Case 6: No ID + no name → proceed, let SQL figure it out."""
        result = await validate_customer(_make_state("My billing is wrong"))
        assert result["customer_found"] is True

    @pytest.mark.asyncio
    async def test_case7_id_not_found_name_fallback(self):
        """Case 7: ID not found but name given → fallback to name search."""
        mock_db = _mock_db_with_customer(None)  # ID #999 not found
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db), \
             patch("app.agent.agents.investigator._search_customers_by_name", new_callable=AsyncMock, return_value=[DAVID]):
            result = await validate_customer(_make_state("Customer #999 David Martinez has an issue"))
        assert result["customer_found"] is True
        assert any("not found" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case8_both_not_found(self):
        """Case 8: ID not found + name not found → stop."""
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(None)):
            result = await validate_customer(_make_state("Customer #999 has a billing issue"))
        assert result["customer_found"] is False
        assert "not found" in result["final_response"].lower()

    @pytest.mark.asyncio
    async def test_suspended_customer_warning(self):
        """Status check: suspended customer proceeds with warning."""
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(EMILY)):
            result = await validate_customer(_make_state("Customer #5 Emily Davis needs help"))
        assert result["customer_found"] is True
        assert any("SUSPENDED" in t for t in result["thought_log"])


# ─────────────────────────────────────────────────────────────
# Async Node Tests — classify_intent (mocked LLM)
# ─────────────────────────────────────────────────────────────


def _mock_llm_response(content: str, input_tokens=100, output_tokens=50):
    """Create a mock LLM response with usage metadata."""
    mock = MagicMock()
    mock.content = content
    mock.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    return mock


def _make_full_state(msg: str, thread_id: str = "test-thread") -> dict:
    """Create a full AgentState dict for testing."""
    return {
        "user_message": msg,
        "thread_id": thread_id,
        "thought_log": [],
    }


class TestClassifyIntentAsync:
    """Test classify_intent with mocked LLM."""

    @pytest.mark.asyncio
    async def test_successful_classification(self):
        mock_response = _mock_llm_response('{"intent": "billing", "confidence": 0.95}')
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.agents.classifier.get_model", return_value=mock_llm), \
             patch("app.agent.agents.classifier.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await classify_intent(_make_full_state("I was charged twice"))

        assert result["intent"] == "billing"
        assert result["intent_confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_json_parse_error_fallback(self):
        mock_response = _mock_llm_response("something unparseable")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.agents.classifier.get_model", return_value=mock_llm), \
             patch("app.agent.agents.classifier.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await classify_intent(_make_full_state("random"))

        assert result["intent"] == "general"
        assert result["intent_confidence"] == 0.3

    @pytest.mark.asyncio
    async def test_tracks_tokens(self):
        mock_response = _mock_llm_response('{"intent": "technical", "confidence": 0.8}')
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.model_name = "llama-3.1-8b-instant"

        mock_metrics = MagicMock()
        with patch("app.agent.agents.classifier.get_model", return_value=mock_llm), \
             patch("app.agent.agents.classifier.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await classify_intent(_make_full_state("Server is slow", "t1"))

        mock_metrics.add_step.assert_called_once()

    @pytest.mark.asyncio
    async def test_simple_intent_adds_groq_indicator(self):
        """Simple intent should add ⚡ Groq routing indicator to thought_log."""
        mock_response = _mock_llm_response('{"intent": "billing", "confidence": 0.9}')
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.agents.classifier.get_model", return_value=mock_llm), \
             patch("app.agent.agents.classifier.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await classify_intent(_make_full_state("Check my balance"))

        assert result["model_provider"] == "groq"
        assert any("⚡" in t for t in result["thought_log"])
        assert any("Groq" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_complex_intent_adds_gemini_indicator(self):
        """Complex intent should add 🧠 Gemini routing indicator to thought_log."""
        mock_response = _mock_llm_response('{"intent": "technical", "confidence": 0.85}')
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.agents.classifier.get_model", return_value=mock_llm), \
             patch("app.agent.agents.classifier.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await classify_intent(_make_full_state("Server keeps crashing"))

        assert result["model_provider"] == "gemini"
        assert any("🧠" in t for t in result["thought_log"])
        assert any("Gemini" in t for t in result["thought_log"])


# ─────────────────────────────────────────────────────────────
# Async Node Tests — write_sql (mocked LLM)
# ─────────────────────────────────────────────────────────────


class TestWriteSqlAsync:
    """Test write_sql with mocked LLM."""

    @pytest.mark.asyncio
    async def test_generates_sql(self):
        mock_response = _mock_llm_response("SELECT * FROM customers WHERE id = 8 LIMIT 20")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("Customer #8 billing issue")
        state["intent"] = "billing"

        with patch("app.agent.agents.investigator.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.investigator.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await write_sql(state)

        assert "SELECT" in result["sql_query"]

    @pytest.mark.asyncio
    async def test_includes_error_context_on_retry(self):
        mock_response = _mock_llm_response("SELECT * FROM customers LIMIT 20")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("Customer issue")
        state["intent"] = "billing"
        state["sql_error"] = "relation 'users' does not exist"
        state["sql_query"] = "SELECT * FROM users"

        with patch("app.agent.agents.investigator.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.investigator.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            await write_sql(state)

        # LLM should have been called with the error context
        call_args = mock_llm.ainvoke.call_args[0][0]
        system_msg = call_args[0].content
        assert "relation" in system_msg or "error" in system_msg.lower()


# ─────────────────────────────────────────────────────────────
# Async Node Tests — execute_sql (mocked DB)
# ─────────────────────────────────────────────────────────────


class TestExecuteSqlAsync:
    """Test execute_sql with mocked Supabase."""

    @pytest.mark.asyncio
    async def test_success(self):
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": [{"id": 8, "name": "David"}]
        })

        state = _make_full_state("query")
        state["sql_query"] = "SELECT * FROM customers WHERE id = 8"

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await execute_sql(state)

        assert result["sql_result"] == [{"id": 8, "name": "David"}]
        assert result["sql_error"] == ""

    @pytest.mark.asyncio
    async def test_failure_increments_retry(self):
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": "relation does not exist",
            "status_code": 400
        })

        state = _make_full_state("query")
        state["sql_query"] = "SELECT * FROM nonexistent"
        state["sql_retry_count"] = 1

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await execute_sql(state)

        assert result["sql_result"] == []
        assert result["sql_retry_count"] == 2

    @pytest.mark.asyncio
    async def test_empty_query(self):
        state = _make_full_state("query")
        state["sql_query"] = ""

        result = await execute_sql(state)
        assert result["sql_error"] == "No SQL query generated"

    @pytest.mark.asyncio
    async def test_error_json_string(self):
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": '{"message": "permission denied"}',
        })

        state = _make_full_state("query")
        state["sql_query"] = "SELECT 1"

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await execute_sql(state)

        assert "permission denied" in result["thought_log"][-1]

    @pytest.mark.asyncio
    async def test_error_dict(self):
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": {"message": "column not found"},
        })

        state = _make_full_state("query")
        state["sql_query"] = "SELECT bad_col FROM customers"

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await execute_sql(state)

        assert "column not found" in result["thought_log"][-1]


# ─────────────────────────────────────────────────────────────
# Async Node Tests — search_docs (mocked DB)
# ─────────────────────────────────────────────────────────────


class TestSearchDocsAsync:
    """Test search_docs with mocked Supabase."""

    @pytest.mark.asyncio
    async def test_docs_found(self):
        mock_db = MagicMock()
        mock_db.search_docs = AsyncMock(return_value=[
            {"title": "Refund Policy", "category": "billing", "content": "Refunds are processed within 5 business days."}
        ])

        state = _make_full_state("refund question")
        state["intent"] = "billing"

        with patch("app.agent.agents.researcher.get_supabase", return_value=mock_db):
            result = await search_docs(state)

        assert "Refund Policy" in result["docs_context"]
        assert result["relevant_docs"] == ["Refund Policy"]

    @pytest.mark.asyncio
    async def test_no_docs_found(self):
        mock_db = MagicMock()
        mock_db.search_docs = AsyncMock(return_value=[])

        state = _make_full_state("obscure question")
        state["intent"] = "general"

        with patch("app.agent.agents.researcher.get_supabase", return_value=mock_db):
            result = await search_docs(state)

        assert "No internal documentation" in result["docs_context"]
        assert result["relevant_docs"] == []


# ─────────────────────────────────────────────────────────────
# Async Node Tests — propose_action (mocked LLM)
# ─────────────────────────────────────────────────────────────


class TestProposeActionAsync:
    """Test propose_action with mocked LLM."""

    @pytest.mark.asyncio
    async def test_valid_proposal(self):
        action_json = json.dumps({
            "type": "refund",
            "amount": 29.99,
            "customer_id": 8,
            "customer_name": "David Martinez",
            "description": "Refund duplicate charge",
            "reason": "Customer was charged twice",
        })
        mock_response = _mock_llm_response(action_json)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("I was double charged")
        state["intent"] = "billing"
        state["sql_result"] = [{"id": 8, "name": "David Martinez", "amount": 29.99}]
        state["docs_context"] = "Refund policy..."

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "refund"
        assert result["proposed_action"]["customer_id"] == 8

    @pytest.mark.asyncio
    async def test_no_customer_forces_escalate(self):
        """If no valid customer in SQL, refund should be forced to escalate."""
        action_json = json.dumps({
            "type": "refund",
            "amount": 50.0,
            "customer_id": 999,
            "customer_name": "Fake Person",
            "description": "Refund request",
            "reason": "Test",
        })
        mock_response = _mock_llm_response(action_json)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("refund please")
        state["intent"] = "billing"
        state["sql_result"] = []  # No customer found
        state["docs_context"] = ""

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "escalate"

    @pytest.mark.asyncio
    async def test_json_parse_error_escalates(self):
        mock_response = _mock_llm_response("I think we should refund them")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("refund")
        state["intent"] = "billing"
        state["sql_result"] = []
        state["docs_context"] = ""

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "escalate"

    @pytest.mark.asyncio
    async def test_propose_action_json_regex_parse_error(self):
        """When LLM returns invalid JSON that matches regex but fails to parse, escalate."""
        # String with curly braces to match regex, but invalid json syntax
        mock_response = _mock_llm_response("Here is the action: { this is not valid json }")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("refund")
        state["intent"] = "billing"
        state["sql_result"] = [{"id": 8, "name": "David Martinez"}]
        state["docs_context"] = ""

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "escalate"

    @pytest.mark.asyncio
    async def test_already_resolved_refund_skips_llm(self):
        """When billing data already contains a 'duplicate' refund, skip LLM and resolve."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock()  # Should NOT be called

        state = _make_full_state("Customer #8 David Martinez says he was charged $49 twice")
        state["intent"] = "billing"
        state["sql_result"] = [
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "refund", "description": "Duplicate charge refund"},
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription (DUPLICATE)"},
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription"},
        ]
        state["docs_context"] = "Refund policy..."

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "resolve"
        assert "already resolved" in result["proposed_action"]["description"].lower()
        assert result["proposed_action"]["customer_id"] == 8
        mock_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_refund_still_calls_llm(self):
        """When billing data has charges only (no refund), LLM should still be called."""
        action_json = json.dumps({
            "type": "refund", "amount": 49.0, "customer_id": 8,
            "customer_name": "David Martinez",
            "description": "Refund duplicate charge", "reason": "Double charge confirmed",
        })
        mock_response = _mock_llm_response(action_json)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("Customer #8 David Martinez says he was charged $49 twice")
        state["intent"] = "billing"
        state["sql_result"] = [
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription (DUPLICATE)"},
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription"},
        ]
        state["docs_context"] = "Refund policy..."

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "refund"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_matching_refund_returns_none(self):
        """When refunds exist but don't match duplicate/double, _detect_already_resolved returns None."""
        from app.agent.agents.resolver import _detect_already_resolved
        sql_result = [
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "refund", "description": "Courtesy credit for downtime"},
        ]
        result = _detect_already_resolved(sql_result, "I was double charged")
        assert result is None

    @pytest.mark.asyncio
    async def test_json_in_markdown_fence_parsed(self):
        """LLM wraps JSON in ```json ... ``` — should still parse correctly."""
        fenced_json = '```json\n{"type": "refund", "amount": 29.99, "customer_id": 8, "customer_name": "David Martinez", "description": "Refund duplicate", "reason": "Double charge"}\n```'
        mock_response = _mock_llm_response(fenced_json)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("I was double charged")
        state["intent"] = "billing"
        state["sql_result"] = [{"id": 8, "name": "David Martinez"}]
        state["docs_context"] = ""

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "refund"
        assert result["proposed_action"]["customer_id"] == 8


# ─────────────────────────────────────────────────────────────
# Async Node Tests — execute_action
# ─────────────────────────────────────────────────────────────


class TestExecuteActionAsync:
    """Test execute_action with recommendation-only output (no DB writes)."""

    @pytest.mark.asyncio
    async def test_refund_result(self):
        state = _make_full_state("refund")
        state["proposed_action"] = {
            "type": "refund", "amount": 29.99,
            "customer_id": 8, "customer_name": "David",
            "description": "Refund duplicate charge",
        }
        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "Refund" in result["execution_result"]
        assert "$29.99" in result["execution_result"]
        assert "recommended" in result["execution_result"]

    @pytest.mark.asyncio
    async def test_credit_result(self):
        state = _make_full_state("credit")
        state["proposed_action"] = {
            "type": "credit", "amount": 10.0,
            "customer_id": 3, "customer_name": "Alice",
            "description": "Apply courtesy credit",
        }
        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "credit" in result["execution_result"].lower()
        assert "$10.00" in result["execution_result"]

    @pytest.mark.asyncio
    async def test_suspend_result(self):
        state = _make_full_state("suspend")
        state["proposed_action"] = {
            "type": "suspend", "customer_id": 5,
            "customer_name": "Emily",
            "description": "Suspend account for policy violation",
        }
        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "suspension" in result["execution_result"].lower()
        assert "Emily" in result["execution_result"]

    @pytest.mark.asyncio
    async def test_reactivate_result(self):
        state = _make_full_state("reactivate")
        state["proposed_action"] = {
            "type": "reactivate", "customer_id": 5,
            "customer_name": "Emily",
            "description": "Reactivate after payment update",
        }
        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "reactivation" in result["execution_result"].lower()
        assert "Emily" in result["execution_result"]

    @pytest.mark.asyncio
    async def test_tier_change_result(self):
        state = _make_full_state("tier change")
        state["proposed_action"] = {
            "type": "tier_change", "customer_id": 3,
            "customer_name": "Charlie",
            "description": "Change to enterprise plan",
        }
        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "Plan change" in result["execution_result"]
        assert "Charlie" in result["execution_result"]

    @pytest.mark.asyncio
    async def test_escalate_without_customer_id(self):
        """Escalate returns descriptive message."""
        state = _make_full_state("escalate")
        state["proposed_action"] = {"type": "escalate", "customer_name": "Bob"}

        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "escalated" in result["execution_result"].lower()

    @pytest.mark.asyncio
    async def test_resolve_result(self):
        """Resolve returns descriptive message."""
        state = _make_full_state("resolve")
        state["proposed_action"] = {"type": "resolve"}

        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert "resolved" in result["execution_result"].lower()

    @pytest.mark.asyncio
    async def test_unknown_action_type(self):
        """Unknown action type returns generic message."""
        state = _make_full_state("unknown")
        state["proposed_action"] = {"type": "unknown_action"}

        with patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = MagicMock()
            result = await execute_action(state)

        assert result["execution_result"] == "Action completed."


# ─────────────────────────────────────────────────────────────
# Async Node Tests — generate_response (mocked LLM)
# ─────────────────────────────────────────────────────────────


class TestGenerateResponseAsync:
    """Test generate_response with mocked LLM."""

    @pytest.mark.asyncio
    async def test_llm_generation(self):
        mock_response = _mock_llm_response("Your refund has been processed.")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        state = _make_full_state("double charge")
        state["intent"] = "billing"
        state["proposed_action"] = {"description": "Refund $29.99"}
        state["approval_status"] = "approved"
        state["execution_result"] = "Refund processed"
        state["sql_result"] = [{"id": 1}]
        state["customer_found"] = True

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await generate_response(state)

        assert result["final_response"] == "Your refund has been processed."

    @pytest.mark.asyncio
    async def test_early_return_for_validation_failure(self):
        """When validate_customer already set final_response, skip LLM."""
        state = _make_full_state("Customer #999 needs help")
        state["customer_found"] = False
        state["final_response"] = "Customer not found"

        result = await generate_response(state)

        assert "final_response" not in result  # Should not overwrite
        assert "skipping llm generation" in result["thought_log"][-1].lower()

    @pytest.mark.asyncio
    async def test_zero_records_path(self):
        """When SQL returned 0 records, generate clear message without LLM."""
        state = _make_full_state("Check billing")
        state["sql_result"] = []
        state["sql_error"] = None
        state["customer_found"] = True

        result = await generate_response(state)

        assert "0 results" in result["final_response"]
        assert "No records" in result["thought_log"][-1]


# ─────────────────────────────────────────────────────────────
# _search_customers_by_name (L122-140)
# ─────────────────────────────────────────────────────────────


class TestSearchCustomersByName:
    """Test _search_customers_by_name helper."""

    @pytest.mark.asyncio
    async def test_multi_word_name(self):
        """Multi-word name → splits into first/last for query."""
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": [{"id": 8, "name": "David Martinez"}],
        })
        result = await _search_customers_by_name(mock_db, "David Martinez")
        assert len(result) == 1
        assert result[0]["name"] == "David Martinez"
        # Verify the SQL used both first and last name
        call_sql = mock_db.execute_sql.call_args[0][0]
        assert "david" in call_sql.lower()
        assert "martinez" in call_sql.lower()

    @pytest.mark.asyncio
    async def test_single_word_name(self):
        """Single-word name → LIKE '%name%' query (L131-136)."""
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": True,
            "data": [{"id": 5, "name": "Emily"}],
        })
        result = await _search_customers_by_name(mock_db, "Emily")
        assert len(result) == 1
        call_sql = mock_db.execute_sql.call_args[0][0]
        assert "emily" in call_sql.lower()

    @pytest.mark.asyncio
    async def test_no_results(self):
        """When execute_sql succeeds but returns empty data (L139-140)."""
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={"success": True, "data": []})
        result = await _search_customers_by_name(mock_db, "Nobody Here")
        assert result == []

    @pytest.mark.asyncio
    async def test_query_failure_returns_empty(self):
        """When execute_sql fails, return empty list."""
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={"success": False, "error": "timeout"})
        result = await _search_customers_by_name(mock_db, "Test User")
        assert result == []


# ─────────────────────────────────────────────────────────────
# validate_customer edge cases for status warnings (L197, L223)
# ─────────────────────────────────────────────────────────────


class TestValidateCustomerSuspendedCases:
    """Cover warning branches that weren't exercised."""

    @pytest.mark.asyncio
    async def test_case4_id_only_suspended(self):
        """Case 4 + suspended: ID only, no name, suspended customer (L197)."""
        suspended_david = {**DAVID, "status": "suspended"}
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(suspended_david)):
            result = await validate_customer(_make_state("Customer #8 has a billing issue"))
        assert result["customer_found"] is True
        assert any("SUSPENDED" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case3_fuzzy_typo_suspended(self):
        """Case 3 + suspended: Fuzzy match with status warning (L223)."""
        suspended_david = {**DAVID, "status": "suspended"}
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(suspended_david)):
            result = await validate_customer(_make_state("Customer #8 Davd Martines was charged twice"))
        assert result["customer_found"] is True
        assert any("typo" in t.lower() for t in result["thought_log"])
        assert any("SUSPENDED" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case5_name_only_no_matches(self):
        """Case 5 name-only → 0 matches → customer not found (L294-306)."""
        mock_db = _mock_db_with_customer(None)
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db), \
             patch("app.agent.agents.investigator._search_customers_by_name", new_callable=AsyncMock, return_value=[]):
            result = await validate_customer(_make_state("Refund requested for Nobody Here"))
        assert result["customer_found"] is False
        assert "Nobody Here" in result["final_response"]


# ─────────────────────────────────────────────────────────────
# execute_sql — non-string/non-dict error type (L431)
# ─────────────────────────────────────────────────────────────


class TestExecuteSqlNonStringError:
    """Cover the else branch for error types that aren't str or dict."""

    @pytest.mark.asyncio
    async def test_error_non_string_type(self):
        """Error is an int → falls through to str(raw_error)[:100] (L431)."""
        mock_db = MagicMock()
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": 42,  # Neither str nor dict
        })
        state = _make_full_state("query")
        state["sql_query"] = "SELECT 1"
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await execute_sql(state)
        assert result["sql_result"] == []
        assert "42" in result["thought_log"][-1]


# ─────────────────────────────────────────────────────────────
# Token tracking for write_sql, propose_action, generate_response
# ─────────────────────────────────────────────────────────────


class TestWriteSqlTokenTracking:
    """Cover L366: write_sql token tracking branch."""

    @pytest.mark.asyncio
    async def test_tracks_tokens(self):
        mock_response = _mock_llm_response("SELECT * FROM customers LIMIT 20")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.model_name = "gpt-4.1"

        state = _make_full_state("Customer #8 billing")
        state["intent"] = "billing"

        mock_metrics = MagicMock()
        with patch("app.agent.agents.investigator.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.investigator.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await write_sql(state)

        mock_metrics.add_step.assert_called_once_with("write_sql", "gpt-4.1", 100, 50)


class TestProposeActionTokenTracking:
    """Cover L561: propose_action token tracking branch."""

    @pytest.mark.asyncio
    async def test_tracks_tokens(self):
        action_json = json.dumps({
            "type": "refund", "amount": 29.99, "customer_id": 8,
            "customer_name": "David Martinez",
            "description": "Refund", "reason": "Double charge",
        })
        mock_response = _mock_llm_response(action_json)
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.model_name = "gpt-4.1"

        state = _make_full_state("I was double charged")
        state["intent"] = "billing"
        state["sql_result"] = [{"id": 8, "name": "David Martinez"}]
        state["docs_context"] = "Refund policy"

        mock_metrics = MagicMock()
        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await propose_action(state)

        mock_metrics.add_step.assert_called_once_with("propose_action", "gpt-4.1", 100, 50)


class TestGenerateResponseTokenTracking:
    """Cover L763: generate_response token tracking branch."""

    @pytest.mark.asyncio
    async def test_tracks_tokens(self):
        mock_response = _mock_llm_response("Resolved.")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.model_name = "llama-3.1-8b-instant"

        state = _make_full_state("billing issue")
        state["intent"] = "billing"
        state["proposed_action"] = {"description": "Refund $29.99"}
        state["approval_status"] = "approved"
        state["execution_result"] = "Refund processed"
        state["sql_result"] = [{"id": 1}]
        state["customer_found"] = True

        mock_metrics = MagicMock()
        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await generate_response(state)

        mock_metrics.add_step.assert_called_once_with(
            "generate_response", "llama-3.1-8b-instant", 100, 50
        )


# ─────────────────────────────────────────────────────────────
# await_approval (L627-656)
# ─────────────────────────────────────────────────────────────


class TestAwaitApprovalAsync:
    """Test await_approval covering auto-approve and interrupt paths."""

    @pytest.mark.asyncio
    async def test_resolve_auto_approves(self):
        """Non-destructive 'resolve' action auto-approves."""
        state = _make_full_state("resolved")
        state["proposed_action"] = {"type": "resolve", "description": "Resolved"}

        result = await await_approval(state)
        assert result["approval_status"] == "approved"
        assert any("auto-approved" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_reactivate_auto_approves(self):
        """Non-destructive 'reactivate' action auto-approves."""
        state = _make_full_state("reactivate")
        state["proposed_action"] = {"type": "reactivate", "description": "Reactivate account"}

        result = await await_approval(state)
        assert result["approval_status"] == "approved"
        assert any("auto-approved" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_dict_decision_approved(self):
        """Destructive action with dict decision → approved."""
        state = _make_full_state("refund")
        state["proposed_action"] = {"type": "refund", "description": "Refund $50"}

        mock_metrics = MagicMock()
        with patch("app.agent.agents.resolver.interrupt", return_value={"approved": True, "reason": ""}), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            result = await await_approval(state)

        assert result["approval_status"] == "approved"
        assert result["denial_reason"] == ""
        # Verify timestamps were set
        assert mock_metrics.hitl_requested_at is not None
        assert mock_metrics.hitl_resolved_at is not None

    @pytest.mark.asyncio
    async def test_dict_decision_denied(self):
        """Destructive action with dict decision → denied with reason."""
        state = _make_full_state("refund")
        state["proposed_action"] = {"type": "refund", "description": "Refund $50"}

        with patch("app.agent.agents.resolver.interrupt", return_value={"approved": False, "reason": "Too expensive"}):
            result = await await_approval(state)
        assert result["approval_status"] == "denied"
        assert result["denial_reason"] == "Too expensive"

    @pytest.mark.asyncio
    async def test_bool_decision(self):
        """Destructive action with bool decision (not dict)."""
        state = _make_full_state("escalate")
        state["proposed_action"] = {"type": "escalate", "description": "Escalate"}

        with patch("app.agent.agents.resolver.interrupt", return_value=True):
            result = await await_approval(state)
        assert result["approval_status"] == "approved"

    @pytest.mark.asyncio
    async def test_bool_decision_denied(self):
        """Bool False → denied with empty reason."""
        state = _make_full_state("refund")
        state["proposed_action"] = {"type": "refund", "description": "Refund"}

        with patch("app.agent.agents.resolver.interrupt", return_value=False):
            result = await await_approval(state)
        assert result["approval_status"] == "denied"
        assert result["denial_reason"] == ""

    @pytest.mark.asyncio
    async def test_suspend_requires_hitl(self):
        """Destructive 'suspend' action requires HITL approval."""
        state = _make_full_state("suspend")
        state["proposed_action"] = {"type": "suspend", "description": "Suspend account"}

        with patch("app.agent.agents.resolver.interrupt", return_value={"approved": True, "reason": ""}) as mock_interrupt:
            result = await await_approval(state)
        mock_interrupt.assert_called_once()
        assert result["approval_status"] == "approved"

