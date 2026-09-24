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


# Found by an adversarial review of the old function DENYLIST: every one of
# these parsed as a single allowlisted-table SELECT and slipped through.
AUDIT_ESCAPES = [
    "SELECT pg_sleep_for('6s')",
    "SELECT pg_sleep_until(now())",
    "SELECT lo_from_bytea(0, 'x')",
    "SELECT pg_advisory_lock(1)",
    "SELECT dblink_connect('host=evil')",
    "SELECT pg_notify('chan', 'x')",
    "SELECT pg_logical_emit_message(true, 'a', 'b')",
    "SELECT database_to_xml(true, true, '')",
    "SELECT table_to_xml('pg_authid', true, true, '')",
    "SELECT pg_ls_waldir()",
    "SELECT version()",
    "SELECT inet_server_addr()",
    "SELECT repeat('a', 1000000000)",
    "SELECT 'customers'::regclass FROM customers",
    "SELECT pg_get_functiondef('f'::regproc)",
    "SELECT * FROM customers WHERE name = pg_read_file('x')",
    "SELECT CASE WHEN true THEN lo_from_bytea(0, 'x') END FROM customers",
    "SELECT NOT pg_try_advisory_lock(1)",
]

REALISTIC = [
    "SELECT c.id, c.name, b.amount FROM customers c JOIN billing b ON b.customer_id = c.id "
    "WHERE c.id = 8 AND b.type = 'charge' OR b.amount > 5 ORDER BY b.created_at DESC LIMIT 20",
    "SELECT COUNT(*) AS n, SUM(amount) FROM billing WHERE customer_id = 8 "
    "AND created_at >= date_trunc('month', now()) - interval '1 month'",
    "SELECT * FROM support_tickets WHERE customer_id = 3 AND status IN ('open', 'in_progress') "
    "AND created_at BETWEEN now() - interval '7 days' AND now()",
    "SELECT CASE WHEN type = 'refund' THEN -amount ELSE amount END AS signed FROM billing "
    "WHERE NOT (status = 'failed') AND description ILIKE '%dup%'",
    "SELECT id, created_at::date, ROUND(amount, 2), string_agg(description, ', ') FROM billing GROUP BY 1, 2, 3",
    "SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) FROM billing",
]


@pytest.mark.parametrize("sql", AUDIT_ESCAPES)
def test_function_allowlist_blocks_audit_escapes(sql):
    result = check_sql(sql)
    assert not result.ok, sql
    assert "not allowed" in result.reason


@pytest.mark.parametrize("sql", REALISTIC)
def test_realistic_investigation_queries_still_pass(sql):
    result = check_sql(sql)
    assert result.ok, result.reason
