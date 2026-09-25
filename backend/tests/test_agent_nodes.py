"""Tests for the agent node functions in app.agent.agents."""

import json

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agent.agents import (
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

    def test_name_leading_the_ticket_is_extracted(self):
        """Regression (eval `edge-name-only`): 'Emily Davis reports…' used to lose
        the name, and identity was then guessed from SQL rows."""
        assert _extract_customer_info("Emily Davis reports a billing issue") == (None, "Emily Davis")
        assert _extract_customer_info("Kevin Lee's account was charged") == (None, "Kevin Lee")

    def test_sentence_openers_are_not_names(self):
        assert _extract_customer_info("Please Help me with billing") == (None, None)
        assert _extract_customer_info("Urgent Request from our team") == (None, None)

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
    mock_db.get_billing = AsyncMock(return_value=[])
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
        # Label is derived from INTENT_MODEL_MAP, so match the model id
        # case-insensitively rather than a hardcoded display name.
        assert any("gemini" in t.lower() for t in result["thought_log"])


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

        with patch("app.agent.agents.investigator.get_model", return_value=mock_llm), \
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

        with patch("app.agent.agents.investigator.get_model", return_value=mock_llm), \
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
        mock_db.get_billing = AsyncMock(return_value=[])
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
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.execute_sql = AsyncMock(return_value={
            "success": False,
            "error": "relation does not exist",
            "status_code": 400
        })

        state = _make_full_state("query")
        state["sql_query"] = "SELECT missing_col FROM customers"
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
        mock_db.get_billing = AsyncMock(return_value=[])
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
        mock_db.get_billing = AsyncMock(return_value=[])
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
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.list_docs = AsyncMock(return_value=[
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
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.list_docs = AsyncMock(return_value=[])

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
        state["customer"] = {"id": 8, "name": "David Martinez", "plan": "pro", "status": "active"}
        state["sql_result"] = [{"id": 71, "customer_id": 8, "amount": 29.99, "type": "charge"}]
        state["billing"] = state["sql_result"]
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
        state["billing"] = state["sql_result"]
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
        state["customer"] = {"id": 8, "name": "David Martinez", "plan": "pro", "status": "active"}
        state["sql_result"] = [{"id": 71, "customer_id": 8, "amount": 29.99, "type": "charge"}]
        state["billing"] = state["sql_result"]
        state["docs_context"] = ""

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "escalate"

    @pytest.mark.asyncio
    async def test_duplicate_refund_on_file_goes_to_a_person_without_the_llm(self):
        """A duplicate-charge complaint with a duplicate refund already on file
        skips the LLM and escalates with that refund as context. It used to
        close as 'already resolved', which hid a second, new duplicate."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock()  # Should NOT be called

        state = _make_full_state("Customer #8 David Martinez says he was charged $49 twice")
        state["intent"] = "billing"
        state["customer"] = {"id": 8, "name": "David Martinez", "plan": "pro", "status": "active"}
        state["sql_result"] = [
            {"id": 30, "customer_id": 8, "amount": "49.00", "type": "refund", "status": "pending", "description": "Duplicate charge refund"},
            {"id": 29, "customer_id": 8, "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription (DUPLICATE)"},
            {"id": 28, "customer_id": 8, "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription"},
        ]
        state["billing"] = state["sql_result"]
        state["docs_context"] = "Refund policy..."

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "escalate"
        assert "duplicate-charge refund already on file ($49.00, pending)" in result["proposed_action"]["description"].lower()
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
        state["customer"] = {"id": 8, "name": "David Martinez", "plan": "pro", "status": "active"}
        state["sql_result"] = [
            {"id": 29, "customer_id": 8, "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription (DUPLICATE)"},
            {"id": 28, "customer_id": 8, "amount": "49.00", "type": "charge", "description": "Pro plan - Monthly subscription"},
        ]
        state["billing"] = state["sql_result"]
        state["docs_context"] = "Refund policy..."

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["type"] == "refund"
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_matching_refund_returns_none(self):
        """When refunds exist but don't match duplicate/double, _duplicate_refund_on_file returns None."""
        from app.agent.agents.resolver import _duplicate_refund_on_file
        sql_result = [
            {"id": 8, "name": "David Martinez", "amount": "49.00", "type": "refund", "description": "Courtesy credit for downtime"},
        ]
        result = _duplicate_refund_on_file(sql_result, None)
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
        state["customer"] = {"id": 8, "name": "David Martinez", "plan": "pro", "status": "active"}
        state["sql_result"] = [{"id": 71, "customer_id": 8, "amount": 29.99, "type": "charge"}]
        state["billing"] = state["sql_result"]
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
        state["billing"] = state["sql_result"]
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
        state["billing"] = state["sql_result"]
        state["sql_error"] = None
        state["customer_found"] = True

        result = await generate_response(state)

        assert "0 results" in result["final_response"]
        assert "No records" in result["thought_log"][-1]


# ─────────────────────────────────────────────────────────────
# _search_customers_by_name
# ─────────────────────────────────────────────────────────────


class TestSearchCustomersByName:
    """_search_customers_by_name delegates to the parameterized REST search."""

    @pytest.mark.asyncio
    async def test_multi_word_name_uses_first_and_last(self):
        mock_db = MagicMock()
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.search_customers = AsyncMock(return_value=[{"id": 8, "name": "David Martinez"}])
        result = await _search_customers_by_name(mock_db, "David Alan Martinez")
        assert result == [{"id": 8, "name": "David Martinez"}]
        mock_db.search_customers.assert_awaited_once_with(["David", "Martinez"])

    @pytest.mark.asyncio
    async def test_single_word_name(self):
        mock_db = MagicMock()
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.search_customers = AsyncMock(return_value=[])
        assert await _search_customers_by_name(mock_db, "Emily") == []
        mock_db.search_customers.assert_awaited_once_with(["Emily"])


# ─────────────────────────────────────────────────────────────
# validate_customer edge cases for status warnings
# ─────────────────────────────────────────────────────────────


class TestValidateCustomerSuspendedCases:
    """Warning branches that weren't exercised."""

    @pytest.mark.asyncio
    async def test_case4_id_only_suspended(self):
        """Case 4 + suspended: ID only, no name, suspended customer."""
        suspended_david = {**DAVID, "status": "suspended"}
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(suspended_david)):
            result = await validate_customer(_make_state("Customer #8 has a billing issue"))
        assert result["customer_found"] is True
        assert any("SUSPENDED" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case3_fuzzy_typo_suspended(self):
        """Case 3 + suspended: Fuzzy match with status warning."""
        suspended_david = {**DAVID, "status": "suspended"}
        with patch("app.agent.agents.investigator.get_supabase", return_value=_mock_db_with_customer(suspended_david)):
            result = await validate_customer(_make_state("Customer #8 Davd Martines was charged twice"))
        assert result["customer_found"] is True
        assert any("typo" in t.lower() for t in result["thought_log"])
        assert any("SUSPENDED" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case5_name_only_no_matches(self):
        """Case 5 name-only → 0 matches → customer not found."""
        mock_db = _mock_db_with_customer(None)
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db), \
             patch("app.agent.agents.investigator._search_customers_by_name", new_callable=AsyncMock, return_value=[]):
            result = await validate_customer(_make_state("Refund requested for Nobody Here"))
        assert result["customer_found"] is False
        assert "Nobody Here" in result["final_response"]


# ─────────────────────────────────────────────────────────────
# execute_sql — non-string/non-dict error type
# ─────────────────────────────────────────────────────────────


class TestExecuteSqlNonStringError:
    """Else branch for error types that aren't str or dict."""

    @pytest.mark.asyncio
    async def test_error_non_string_type(self):
        """Error is an int → falls through to str(raw_error)[:100]."""
        mock_db = MagicMock()
        mock_db.get_billing = AsyncMock(return_value=[])
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
    """write_sql token tracking branch."""

    @pytest.mark.asyncio
    async def test_tracks_tokens(self):
        mock_response = _mock_llm_response("SELECT * FROM customers LIMIT 20")
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.model_name = "gpt-4.1"

        state = _make_full_state("Customer #8 billing")
        state["intent"] = "billing"

        mock_metrics = MagicMock()
        with patch("app.agent.agents.investigator.get_model", return_value=mock_llm), \
             patch("app.agent.agents.investigator.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await write_sql(state)

        mock_metrics.add_step.assert_called_once_with("write_sql", "gpt-4.1", 100, 50)


class TestProposeActionTokenTracking:
    """propose_action token tracking branch."""

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
        state["billing"] = state["sql_result"]
        state["docs_context"] = "Refund policy"

        mock_metrics = MagicMock()
        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await propose_action(state)

        mock_metrics.add_step.assert_called_once_with("propose_action", "gpt-4.1", 100, 50)


class TestGenerateResponseTokenTracking:
    """generate_response token tracking branch."""

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
        state["billing"] = state["sql_result"]
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
# await_approval
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
    async def test_reactivate_requires_human_approval(self):
        """Regression: 'reactivate' must NOT auto-approve.

        Pins the v2.0.0 breaking change. Reactivating a suspended or cancelled
        account undoes a compliance action and resumes billing, so it goes
        through the human gate rather than completing autonomously.
        """
        state = _make_full_state("reactivate")
        state["proposed_action"] = {"type": "reactivate", "description": "Reactivate account"}

        with patch("app.agent.agents.resolver.interrupt") as mock_interrupt, \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_interrupt.return_value = {"approved": True, "reason": "ok"}
            mock_tracker.return_value.get_request.return_value = None

            result = await await_approval(state)

        mock_interrupt.assert_called_once()
        assert result["approval_status"] == "approved"
        assert not any("auto-approved" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_dict_decision_approved(self):
        """Destructive action with dict decision → approved."""
        state = _make_full_state("refund")
        state["proposed_action"] = {"type": "refund", "description": "Refund $50"}

        mock_metrics = MagicMock()
        mock_metrics.hitl_requested_at = None
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

    @pytest.mark.asyncio
    async def test_hitl_requested_at_not_overwritten_if_already_set(self):
        """If hitl_requested_at was already set (e.g. by a prior interrupt cycle on
        resume), await_approval must NOT clobber it with a new timestamp."""
        state = _make_full_state("refund")
        state["proposed_action"] = {"type": "refund", "description": "Refund $50"}

        mock_metrics = MagicMock()
        original_requested_at = 12345.0
        mock_metrics.hitl_requested_at = original_requested_at

        with patch("app.agent.agents.resolver.interrupt", return_value={"approved": True, "reason": ""}), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            result = await await_approval(state)

        assert result["approval_status"] == "approved"
        # Unchanged — the "not metrics.hitl_requested_at" guard should have skipped reassignment
        assert mock_metrics.hitl_requested_at == original_requested_at


# ─────────────────────────────────────────────────────────────
# model_name fallback branch (hasattr(llm, "model_name") is False)
# ─────────────────────────────────────────────────────────────


class _LLMWithoutModelNameAttr:
    """A minimal LLM stand-in that deliberately lacks a `model_name` attribute,
    forcing callers to fall back to `str(llm.model)`."""

    def __init__(self, response):
        self._response = response
        self.model = "raw-model-object"

    async def ainvoke(self, messages):
        return self._response


class TestClassifyIntentModelNameFallback:
    """`else str(llm.model)` branch in classify_intent."""

    @pytest.mark.asyncio
    async def test_falls_back_to_str_model_when_no_model_name_attr(self):
        mock_response = _mock_llm_response('{"intent": "billing", "confidence": 0.9}')
        llm = _LLMWithoutModelNameAttr(mock_response)
        mock_metrics = MagicMock()

        with patch("app.agent.agents.classifier.get_model", return_value=llm), \
             patch("app.agent.agents.classifier.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await classify_intent(_make_full_state("billing question"))

        mock_metrics.add_step.assert_called_once_with(
            "classify_intent", "raw-model-object", 100, 50
        )


class TestWriteSqlModelNameFallback:
    """`else str(llm.model)` branch in write_sql."""

    @pytest.mark.asyncio
    async def test_falls_back_to_str_model_when_no_model_name_attr(self):
        mock_response = _mock_llm_response("SELECT * FROM customers LIMIT 20")
        llm = _LLMWithoutModelNameAttr(mock_response)
        mock_metrics = MagicMock()

        state = _make_full_state("Customer #8 billing")
        state["intent"] = "billing"

        with patch("app.agent.agents.investigator.get_model", return_value=llm), \
             patch("app.agent.agents.investigator.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await write_sql(state)

        mock_metrics.add_step.assert_called_once_with(
            "write_sql", "raw-model-object", 100, 50
        )


class TestProposeActionModelNameFallback:
    """`else str(llm.model)` branch in propose_action."""

    @pytest.mark.asyncio
    async def test_falls_back_to_str_model_when_no_model_name_attr(self):
        action_json = json.dumps({
            "type": "refund", "amount": 29.99, "customer_id": 8,
            "customer_name": "David Martinez",
            "description": "Refund", "reason": "Double charge",
        })
        mock_response = _mock_llm_response(action_json)
        llm = _LLMWithoutModelNameAttr(mock_response)
        mock_metrics = MagicMock()

        state = _make_full_state("I was double charged")
        state["intent"] = "billing"
        state["sql_result"] = [{"id": 8, "name": "David Martinez"}]
        state["billing"] = state["sql_result"]
        state["docs_context"] = "Refund policy"

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await propose_action(state)

        mock_metrics.add_step.assert_called_once_with(
            "propose_action", "raw-model-object", 100, 50
        )


class TestGenerateResponseModelNameFallback:
    """`else str(llm.model)` branch in generate_response."""

    @pytest.mark.asyncio
    async def test_falls_back_to_str_model_when_no_model_name_attr(self):
        mock_response = _mock_llm_response("Resolved.")
        llm = _LLMWithoutModelNameAttr(mock_response)
        mock_metrics = MagicMock()

        state = _make_full_state("billing issue")
        state["intent"] = "billing"
        state["proposed_action"] = {"description": "Refund $29.99"}
        state["approval_status"] = "approved"
        state["execution_result"] = "Refund processed"
        state["sql_result"] = [{"id": 1}]
        state["billing"] = state["sql_result"]
        state["customer_found"] = True

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = mock_metrics
            await generate_response(state)

        mock_metrics.add_step.assert_called_once_with(
            "generate_response", "raw-model-object", 100, 50
        )


# ─────────────────────────────────────────────────────────────
# _duplicate_refund_on_file edge cases
# ─────────────────────────────────────────────────────────────


class TestDuplicateRefundOnFileEdgeCases:
    """Additional branch coverage for _duplicate_refund_on_file."""

    def test_credit_type_with_duplicate_keyword_detected(self):
        """A 'credit' record (not just 'refund') mentioning 'duplicate' counts
        too (the type filter includes credit), and it escalates."""
        from app.agent.agents.resolver import _duplicate_refund_on_file

        sql_result = [
            {"id": 44, "customer_id": 8, "amount": "15.00", "type": "credit",
             "description": "Courtesy credit for duplicate billing"},
        ]
        result = _duplicate_refund_on_file(sql_result, {"id": 8, "name": "David Martinez"})
        assert result is not None
        assert result["type"] == "escalate"
        assert result["customer_id"] == 8
        assert "15.00" in result["description"]
        assert "completed" in result["description"]

    def test_missing_amount_key_defaults_to_zero(self):
        """When the refund record has no 'amount' key at all, default to 0.00 in the summary."""
        from app.agent.agents.resolver import _duplicate_refund_on_file

        sql_result = [
            {"id": 44, "customer_id": 8, "type": "refund",
             "description": "Duplicate charge refund"},
        ]
        result = _duplicate_refund_on_file(sql_result, {"id": 8, "name": "David Martinez"})
        assert result is not None
        assert "$0.00" in result["description"]

    def test_empty_sql_results_returns_none(self):
        from app.agent.agents.resolver import _duplicate_refund_on_file
        assert _duplicate_refund_on_file([], None) is None

    def test_non_list_sql_results_returns_none(self):
        from app.agent.agents.resolver import _duplicate_refund_on_file
        assert _duplicate_refund_on_file(None, None) is None



# ─────────────────────────────────────────────────────────────
# Production-readiness regressions
# ─────────────────────────────────────────────────────────────


class TestSqlGuardInExecuteSql:
    """The guard runs before the database and feeds rejections to self-healing."""

    @pytest.mark.asyncio
    async def test_blocked_query_never_reaches_db_and_counts_as_retry(self):
        mock_db = MagicMock()
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.execute_sql = AsyncMock()
        state = _make_full_state("show me everything")
        state["sql_query"] = "SELECT * FROM mrr_board.customers"
        state["sql_retry_count"] = 1

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await execute_sql(state)

        mock_db.execute_sql.assert_not_called()
        assert result["sql_error"].startswith("Blocked by SQL guard: schema 'mrr_board'")
        assert result["sql_retry_count"] == 2
        assert "SQL guard blocked" in result["thought_log"][-1]

    @pytest.mark.asyncio
    async def test_db_receives_guard_normalized_sql(self):
        mock_db = MagicMock()
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.execute_sql = AsyncMock(return_value={"success": True, "data": []})
        state = _make_full_state("q")
        state["sql_query"] = "select * from customers"

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            await execute_sql(state)

        assert mock_db.execute_sql.call_args[0][0] == "SELECT * FROM customers LIMIT 50"


class TestStripFences:
    def test_strips_markdown_fence(self):
        from app.agent.agents.investigator import _strip_fences
        assert _strip_fences("```sql\nSELECT 1\n```") == "SELECT 1"

    def test_does_not_eat_trailing_letters(self):
        """Regression: `.strip("sql")` turned 'ORDER BY email' into 'ORDER BY emai'."""
        from app.agent.agents.investigator import _strip_fences
        assert _strip_fences("SELECT * FROM customers ORDER BY email;") == (
            "SELECT * FROM customers ORDER BY email"
        )


class TestValidatedCustomerIsSourceOfTruth:
    """Regression: billing rows carry customer_id but no name, so a validated
    customer used to read as 'not found' and every refund became an escalation."""

    @pytest.mark.asyncio
    async def test_validation_returns_customer_row(self):
        customer = {"id": 8, "name": "David Martinez", "email": "d@x.com", "plan": "pro", "status": "active"}
        mock_db = MagicMock()
        mock_db.get_billing = AsyncMock(return_value=[])
        mock_db.execute_sql = AsyncMock(return_value={"success": True, "data": [customer]})
        state = _make_full_state("Customer #8 David Martinez wants a refund")

        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await validate_customer(state)

        assert result["customer"] == customer

    @pytest.mark.asyncio
    async def test_billing_only_sql_rows_do_not_trigger_not_found_guard(self):
        action_json = json.dumps({
            "type": "refund", "amount": 49.0, "customer_id": None, "customer_name": "?",
            "description": "Refund duplicate charge", "reason": "Two identical charges",
        })
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(action_json))

        state = _make_full_state("Customer #8 was charged twice")
        state["customer"] = {"id": 8, "name": "David Martinez", "plan": "pro", "status": "active"}
        state["sql_result"] = [
            {"customer_id": 8, "amount": 49.0, "type": "charge"},
            {"customer_id": 8, "amount": 49.0, "type": "charge"},
        ]
        state["billing"] = state["sql_result"]

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        prompt = mock_llm.ainvoke.call_args[0][0]
        assert "NO matching customer" not in prompt[0].content
        assert '"name": "David Martinez"' in prompt[1].content
        assert result["proposed_action"]["type"] == "refund"
        assert result["proposed_action"]["customer_id"] == 8
        assert result["proposed_action"]["customer_name"] == "David Martinez"


class TestValidatedCustomerFlowsDownstream:
    """Regression (eval `edge-wrong-id-right-name`): validation corrected #777 →
    #12 but the SQL writer trusted the ticket and queried customer_id = 777."""

    @pytest.mark.asyncio
    async def test_sql_writer_is_told_the_validated_id(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response("SELECT * FROM billing WHERE customer_id = 12"))
        state = _make_full_state("Customer #777 Kevin Lee asks why he was charged")
        state["customer"] = {"id": 12, "name": "Kevin Lee"}

        with patch("app.agent.agents.investigator.get_model", return_value=mock_llm), \
             patch("app.agent.agents.investigator.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            await write_sql(state)

        human = mock_llm.ainvoke.call_args[0][0][1].content
        assert "Use customer_id = 12" in human

    @pytest.mark.asyncio
    async def test_no_hint_without_validated_customer(self):
        from app.agent.agents.investigator import _validated_customer_hint
        assert _validated_customer_hint({}) == ""

    @pytest.mark.asyncio
    async def test_zero_records_message_names_the_customer_not_the_ticket(self):
        state = _make_full_state("Customer #12 Kevin Lee asks about a charge")
        state.update({"customer_found": True, "sql_result": [], "sql_error": "",
                      "customer": {"id": 12, "name": "Kevin Lee"}})
        result = await generate_response(state)
        assert "for Customer #12 Kevin Lee." in result["final_response"]
        assert "asks about a charge" not in result["final_response"]

    @pytest.mark.asyncio
    async def test_zero_records_message_without_customer(self):
        state = _make_full_state("What is the refund policy?")
        state.update({"customer_found": True, "sql_result": [], "sql_error": ""})
        result = await generate_response(state)
        assert "for this request." in result["final_response"]


class TestRankDocs:
    """Regression (eval `core-outage-credit-4`): retrieval keyed on the intent
    word alone never surfaced the outage policy, so the agent invented $5."""

    DOCS = [
        {"title": "Refund Policy", "category": "billing", "content": "Refunds within 30 days of charge."},
        {"title": "Compensation Guidelines for Outages", "category": "billing",
         "content": "Major outage (4-24 hours): 50% monthly credit."},
        {"title": "API Rate Limits", "category": "technical", "content": "Enterprise: 10K requests/min."},
        {"title": "Password Reset Troubleshooting", "category": "account", "content": "Check spam folder."},
    ]

    def test_outage_ticket_surfaces_outage_policy_first(self):
        from app.agent.agents.researcher import rank_docs
        ranked = rank_docs(self.DOCS, "Customer #4 had a 6-hour outage and asks about compensation", "billing")
        assert ranked[0]["title"] == "Compensation Guidelines for Outages"

    def test_irrelevant_docs_are_excluded(self):
        from app.agent.agents.researcher import rank_docs
        ranked = rank_docs(self.DOCS, "hitting API rate limits", "technical")
        assert [d["title"] for d in ranked] == ["API Rate Limits"]

    def test_intent_breaks_ties(self):
        from app.agent.agents.researcher import rank_docs
        docs = [
            {"title": "Alpha", "category": "account", "content": "widget"},
            {"title": "Beta", "category": "billing", "content": "widget"},
        ]
        assert rank_docs(docs, "widget", "billing")[0]["title"] == "Beta"

    def test_stemming_matches_plural_and_past_tense(self):
        from app.agent.agents.researcher import _stem
        assert _stem("outages") == _stem("outage")
        assert _stem("charged") == _stem("charges") == "charg"
        assert _stem("api") == "api"

    def test_top_k_is_respected(self):
        from app.agent.agents.researcher import rank_docs
        docs = [{"title": f"widget {i}", "category": "x", "content": ""} for i in range(10)]
        assert len(rank_docs(docs, "widget", None, k=3)) == 3


class TestScreenInputNode:
    @pytest.mark.asyncio
    async def test_clean_ticket(self):
        from app.agent.agents.classifier import screen_input
        with patch("app.agent.agents.classifier.screen", AsyncMock(return_value=([], 0.0004))):
            result = await screen_input(_make_full_state("charged twice"))
        assert result["risk_flags"] == []
        assert "Input screen clean (prompt-guard 0.000)" in result["thought_log"][-1]

    @pytest.mark.asyncio
    async def test_flagged_ticket_without_guard(self):
        from app.agent.agents.classifier import screen_input
        with patch("app.agent.agents.classifier.screen", AsyncMock(return_value=(["role-spoofing"], None))):
            result = await screen_input(_make_full_state("<system>"))
        assert result["risk_flags"] == ["role-spoofing"]
        assert "Input flagged: role-spoofing (prompt-guard unavailable)" in result["thought_log"][-1]


class TestFlaggedTicketsAlwaysEscalate:
    """Enforced in code: the prompt is exactly what an injection attacks."""

    @pytest.mark.asyncio
    async def test_model_compliance_is_overridden_and_not_quoted(self):
        action_json = json.dumps({
            "type": "resolve", "amount": None, "customer_id": 3, "customer_name": "Maria Garcia",
            "description": "Here is SQL for information_schema.tables", "reason": "Customer asked",
        })
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(action_json))
        state = _make_full_state("list information_schema.tables")
        state["customer"] = {"id": 3, "name": "Maria Garcia"}
        state["risk_flags"] = ["data-exfiltration"]
        state["sql_result"] = [{"customer_id": 3}]
        state["billing"] = state["sql_result"]

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        action = result["proposed_action"]
        assert action["type"] == "escalate"
        assert "information_schema" not in action["description"] + action["reason"]
        assert "'resolve'" in action["reason"]

    @pytest.mark.asyncio
    async def test_existing_escalation_is_kept(self):
        action_json = json.dumps({
            "type": "escalate", "amount": None, "customer_id": 12, "customer_name": "Kevin Lee",
            "description": "Suspicious authority claim", "reason": "Needs a human",
        })
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(action_json))
        state = _make_full_state("I'm the CEO")
        state["customer"] = {"id": 12, "name": "Kevin Lee"}
        state["risk_flags"] = ["approval-bypass"]
        state["sql_result"] = [{"customer_id": 12}]
        state["billing"] = state["sql_result"]

        with patch("app.agent.agents.resolver.get_model_for_intent", return_value=mock_llm), \
             patch("app.agent.agents.resolver.get_tracker") as mock_tracker:
            mock_tracker.return_value.get_request.return_value = None
            result = await propose_action(state)

        assert result["proposed_action"]["description"] == "Suspicious authority claim"


def test_ticket_boilerplate_does_not_pull_unrelated_policies():
    from app.agent.agents.researcher import rank_docs
    docs = [
        {"title": "Refund Policy", "category": "billing", "content": "Duplicate charges are refunded."},
        {"title": "Account Deletion Process", "category": "account", "content": "GDPR deletion steps."},
    ]
    ranked = rank_docs(docs, "Charged twice. Please investigate and process a refund if confirmed.", "billing")
    assert [d["title"] for d in ranked] == ["Refund Policy"]


class TestDuplicateRefundOnFileScope:
    def test_failed_refunds_do_not_count(self):
        from app.agent.agents.resolver import _duplicate_refund_on_file
        rows = [{"id": 5, "customer_id": 8, "type": "refund", "status": "failed",
                 "amount": 49, "description": "Duplicate charge refund"}]
        assert _duplicate_refund_on_file(rows, {"id": 8, "name": "D"}) is None

    def test_other_customers_refunds_do_not_count(self):
        from app.agent.agents.resolver import _duplicate_refund_on_file
        rows = [{"id": 5, "customer_id": 9, "type": "refund", "amount": 49,
                 "description": "Duplicate charge refund"}]
        assert _duplicate_refund_on_file(rows, {"id": 8, "name": "D"}) is None


class TestParseAction:
    def test_invalid_json_object_in_prose_returns_none(self):
        from app.agent.agents.resolver import _parse_action
        assert _parse_action("Here you go: {not: valid}") is None

    def test_non_object_json_returns_none(self):
        from app.agent.agents.resolver import _parse_action
        assert _parse_action('["refund"]') is None

    def test_trailing_json_keyword_is_not_eaten(self):
        """Regression: .strip("json") stripped characters, not a prefix."""
        from app.agent.agents.resolver import _parse_action
        assert _parse_action('```json\n{"type": "resolve", "note": "sent json"}\n```') == {
            "type": "resolve", "note": "sent json"}


def test_parse_action_extracts_json_from_prose():
    from app.agent.agents.resolver import _parse_action
    assert _parse_action('Sure! {"type": "resolve"} Hope that helps.') == {"type": "resolve"}


class TestBillingEvidence:
    """Regression (final eval): the refund ceiling read the model's SQL rows,
    whose column names the model chooses (b.type AS billing_type) — every
    legitimate refund escalated. Billing is now fetched at validation."""

    @pytest.mark.asyncio
    async def test_validation_fetches_billing_for_the_verified_customer(self):
        mock_db = _mock_db_with_customer(DAVID)
        mock_db.get_billing = AsyncMock(return_value=[{"id": 1, "customer_id": 8, "amount": 49, "type": "charge"}])
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await validate_customer(_make_state("Customer #8 David Martinez was double charged"))
        assert result["billing"][0]["amount"] == 49
        mock_db.get_billing.assert_awaited_once_with(8)

    @pytest.mark.asyncio
    async def test_no_billing_fetch_without_a_verified_customer(self):
        mock_db = _mock_db_with_customer(None)
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await validate_customer(_make_state("What is your refund policy?"))
        assert "billing" not in result
        mock_db.get_billing.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_guessed_leading_name_with_no_match_is_not_a_stop(self):
        """'Dark Mode is broken' looks like a name; unmatched, it's just a ticket."""
        mock_db = _mock_db_with_customer(None)
        mock_db.search_customers = AsyncMock(return_value=[])
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await validate_customer(_make_state("Dark Mode is broken on mobile"))
        assert result["customer_found"] is True
        assert "No specific customer" in result["thought_log"][-1]

    @pytest.mark.asyncio
    async def test_explicit_unmatched_name_still_stops(self):
        mock_db = _mock_db_with_customer(None)
        mock_db.search_customers = AsyncMock(return_value=[])
        with patch("app.agent.agents.investigator.get_supabase", return_value=mock_db):
            result = await validate_customer(_make_state("Refund the charge for Zelda Quixote"))
        assert result["customer_found"] is False
