"""Application-side guard for LLM-generated SQL.

The model writes SQL; nothing it writes is trusted. This is the first of
three independent layers, and it is the only one that can explain a rejection
back to the model so the self-healing loop can repair the query:

  1. This guard  — parse with sqlglot, allow exactly one read-only SELECT over
                   an allowlist of tables, deny side-effecting functions,
                   bound the row count.
  2. Postgres    — `execute_readonly_query` rejects non-SELECT text and runs
                   with a 5s statement_timeout.
  3. Privileges  — that function is owned by `aegis_query`, a NOLOGIN role
                   granted SELECT on the four Aegis tables and nothing else.

Any one layer failing open is caught by the next.
"""

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

ALLOWED_TABLES = frozenset({"customers", "billing", "support_tickets", "internal_docs"})

# Functions with side effects or that reach outside the query's own data.
DENIED_FUNCTIONS = frozenset({
    "pg_sleep", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "pg_stat_file",
    "lo_import", "lo_export", "lo_get", "dblink", "dblink_exec", "set_config",
    "current_setting", "pg_terminate_backend", "pg_cancel_backend", "pg_reload_conf",
    "txid_current", "nextval", "setval", "query_to_xml", "copy",
})

MAX_ROWS = 50


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    sql: str = ""
    reason: str = ""


def _reject(reason: str) -> GuardResult:
    return GuardResult(ok=False, reason=reason)


def check_sql(sql: str) -> GuardResult:
    """Validate one LLM-generated query. Returns normalized SQL when allowed."""
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        return _reject("empty query")

    try:
        statements = [s for s in sqlglot.parse(text, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        return _reject(f"could not parse SQL: {str(e).splitlines()[0]}")

    if len(statements) != 1:
        return _reject(f"exactly one statement allowed, got {len(statements)}")

    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        return _reject(f"only SELECT is allowed, got {tree.key.upper()}")

    # Any write/DDL node anywhere in the tree (e.g. inside a CTE) is fatal.
    for node_type in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
                      exp.Alter, exp.Command, exp.Merge, exp.TruncateTable):
        if tree.find(node_type):
            return _reject(f"{node_type.__name__.upper()} is not allowed")

    if tree.find(exp.Lock):
        return _reject("row locking (FOR UPDATE/SHARE) is not allowed")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = (table.db or "").lower()
        if schema and schema != "public":
            return _reject(f"schema '{schema}' is not allowed")
        if name in cte_names and not schema:
            continue
        if name not in ALLOWED_TABLES:
            allowed = ", ".join(sorted(ALLOWED_TABLES))
            return _reject(f"table '{name}' is not allowed (allowed: {allowed})")

    for func in tree.find_all(exp.Func):
        fname = (func.sql_name() if not isinstance(func, exp.Anonymous) else func.name).lower()
        if fname in DENIED_FUNCTIONS:
            return _reject(f"function '{fname}' is not allowed")

    # Bound the result size at the outermost level.
    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_ROWS)
    else:
        bound = limit.expression
        value = int(bound.name) if isinstance(bound, exp.Literal) and bound.is_int else MAX_ROWS + 1
        if value > MAX_ROWS:
            tree = tree.limit(MAX_ROWS)

    return GuardResult(ok=True, sql=tree.sql(dialect="postgres"))
