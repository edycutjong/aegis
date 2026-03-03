"""Tests for pure-logic functions in app.agent.nodes."""

from app.agent.nodes import should_retry_sql, should_execute


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

from app.agent.nodes import (
    _extract_customer_info,
    _fuzzy_name_match,
    _status_warning,
    should_proceed_after_validation,
)


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

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent.nodes import validate_customer


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
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 David Martinez was charged twice"))
        assert result["customer_found"] is True
        assert any("validated" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case2_id_and_name_mismatch(self):
        """Case 2: ID exists + wrong name → customer_found=False."""
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 Sarah Chen was charged twice"))
        assert result["customer_found"] is False
        assert "David Martinez" in result["final_response"]
        assert "Sarah Chen" in result["final_response"]

    @pytest.mark.asyncio
    async def test_case3_fuzzy_typo(self):
        """Case 3: ID + typo name → auto-correct, customer_found=True."""
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 Davd Martines was charged twice"))
        assert result["customer_found"] is True
        assert any("typo" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case4_id_only(self):
        """Case 4: ID only, no name → customer_found=True."""
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(DAVID)):
            result = await validate_customer(_make_state("Customer #8 has been charged twice"))
        assert result["customer_found"] is True

    @pytest.mark.asyncio
    async def test_case5_name_only_single_match(self):
        """Case 5: No ID + name → single match found, customer_found=True."""
        mock_db = _mock_db_with_customer(None)  # No ID lookup needed
        with patch("app.agent.nodes.get_supabase", return_value=mock_db), \
             patch("app.agent.nodes._search_customers_by_name", new_callable=AsyncMock, return_value=[EMILY]):
            result = await validate_customer(_make_state("Refund requested for Emily Davis"))
        assert result["customer_found"] is True
        assert any("found by name" in t for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case5_name_only_multiple_matches(self):
        """Case 5: No ID + name → multiple matches, returns candidates for disambiguation."""
        emily2 = {"id": 15, "name": "Emily Davidson", "email": "e2@example.com", "plan": "basic", "status": "active"}
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(None)), \
             patch("app.agent.nodes._search_customers_by_name", new_callable=AsyncMock, return_value=[EMILY, emily2]):
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
        with patch("app.agent.nodes.get_supabase", return_value=mock_db), \
             patch("app.agent.nodes._search_customers_by_name", new_callable=AsyncMock, return_value=[DAVID]):
            result = await validate_customer(_make_state("Customer #999 David Martinez has an issue"))
        assert result["customer_found"] is True
        assert any("not found" in t.lower() for t in result["thought_log"])

    @pytest.mark.asyncio
    async def test_case8_both_not_found(self):
        """Case 8: ID not found + name not found → stop."""
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(None)):
            result = await validate_customer(_make_state("Customer #999 has a billing issue"))
        assert result["customer_found"] is False
        assert "not found" in result["final_response"].lower()

    @pytest.mark.asyncio
    async def test_suspended_customer_warning(self):
        """Status check: suspended customer proceeds with warning."""
        with patch("app.agent.nodes.get_supabase", return_value=_mock_db_with_customer(EMILY)):
            result = await validate_customer(_make_state("Customer #5 Emily Davis needs help"))
        assert result["customer_found"] is True
        assert any("SUSPENDED" in t for t in result["thought_log"])
