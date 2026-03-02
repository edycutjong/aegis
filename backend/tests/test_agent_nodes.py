"""Tests for pure-logic functions in app.agent.nodes."""

from app.agent.nodes import should_retry_sql, should_execute


class TestShouldRetrySql:
    """Conditional edge: retry SQL on error (up to 3 attempts)."""

    def test_retries_when_error_and_under_limit(self):
        state = {"sql_error": "relation does not exist", "sql_retry_count": 1}
        assert should_retry_sql(state) == "write_sql"

    def test_stops_retrying_at_limit(self):
        state = {"sql_error": "syntax error", "sql_retry_count": 3}
        assert should_retry_sql(state) == "search_docs"

    def test_proceeds_when_no_error(self):
        state = {"sql_error": "", "sql_retry_count": 0}
        assert should_retry_sql(state) == "search_docs"

    def test_proceeds_when_error_is_none(self):
        state = {}
        assert should_retry_sql(state) == "search_docs"


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
