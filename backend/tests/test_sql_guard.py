"""Tests for app.db.sql_guard — the app-side firewall for LLM-written SQL.

The attack corpus is the point: each case is something a model has been
observed to write, or an injected ticket could coax it into writing.
"""

import pytest

from app.db.sql_guard import MAX_ROWS, check_sql


ALLOWED = [
    "SELECT * FROM customers WHERE id = 8",
    "select c.name, b.amount from customers c join billing b on b.customer_id = c.id where c.id = 8",
    "WITH recent AS (SELECT * FROM billing WHERE customer_id = 8) SELECT * FROM recent",
    "SELECT * FROM billing UNION SELECT * FROM billing",
    "SELECT * FROM public.customers",
    "SELECT COUNT(*) FROM support_tickets",
    "SELECT title FROM internal_docs WHERE category = 'billing';",
]

BLOCKED = [
    ("", "empty query"),
    ("SELECT * FROM customers; DROP TABLE customers", "exactly one statement"),
    ("DELETE FROM customers", "only SELECT"),
    ("UPDATE customers SET plan = 'enterprise'", "only SELECT"),
    ("INSERT INTO billing (amount) VALUES (1)", "only SELECT"),
    ("WITH d AS (DELETE FROM billing RETURNING *) SELECT * FROM d", "DELETE"),
    ("SELECT * FROM mrr_board.customers", "schema 'mrr_board'"),
    ("SELECT * FROM auth.users", "schema 'auth'"),
    ("SELECT * FROM (SELECT * FROM auth.users) t", "schema 'auth'"),
    ("SELECT usename FROM pg_catalog.pg_user", "schema 'pg_catalog'"),
    ("SELECT * FROM pg_user", "table 'pg_user'"),
    ("SELECT * FROM information_schema.tables", "schema 'information_schema'"),
    ("SELECT pg_sleep(10)", "function 'pg_sleep'"),
    ("SELECT pg_read_file('/etc/passwd')", "function 'pg_read_file'"),
    ("SELECT current_setting('app.secret')", "function 'current_setting'"),
    ("SELECT set_config('role', 'postgres', false)", "function 'set_config'"),
    ("SELECT * FROM customers FOR UPDATE", "row locking"),
    ("SELECT * FROM (", "could not parse"),
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allows_read_only_queries_over_allowlisted_tables(sql):
    result = check_sql(sql)
    assert result.ok, result.reason
    assert result.sql.upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize("sql,reason", BLOCKED)
def test_blocks_unsafe_queries_with_an_explainable_reason(sql, reason):
    result = check_sql(sql)
    assert not result.ok
    assert reason in result.reason
    assert result.sql == ""


def test_cte_name_shadowing_an_allowlisted_table_is_fine():
    assert check_sql("WITH billing AS (SELECT * FROM customers) SELECT * FROM billing").ok


def test_adds_row_bound_when_missing():
    assert check_sql("SELECT * FROM customers").sql.endswith(f"LIMIT {MAX_ROWS}")


def test_clamps_oversized_limit():
    assert check_sql("SELECT * FROM customers LIMIT 100000").sql.endswith(f"LIMIT {MAX_ROWS}")


def test_keeps_small_limit():
    assert check_sql("SELECT * FROM customers LIMIT 5").sql.endswith("LIMIT 5")


def test_non_numeric_limit_is_clamped():
    assert check_sql("SELECT * FROM customers LIMIT ALL").sql.endswith(f"LIMIT {MAX_ROWS}")


def test_expression_limit_is_clamped():
    assert check_sql("SELECT * FROM customers LIMIT 2 + 2").sql.endswith(f"LIMIT {MAX_ROWS}")


def test_rejects_non_select_statement_that_parses_as_command():
    result = check_sql("VACUUM customers")
    assert not result.ok


def test_every_blocked_query_is_also_rejected_when_trailing_semicolon_added():
    for sql, _ in BLOCKED:
        if sql:
            assert not check_sql(sql + ";").ok
