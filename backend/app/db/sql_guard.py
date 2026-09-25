"""Application-side guard for LLM-generated SQL.

The model writes SQL; nothing it writes is trusted. This is the first of
three independent layers, and it is the only one that can explain a rejection
back to the model so the self-healing loop can repair the query:

  1. This guard  — parse with sqlglot, allow exactly one read-only SELECT over
                   an allowlist of tables and an allowlist of functions,
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

# Functions are ALLOWLISTED, not denylisted: Postgres grants EXECUTE on
# hundreds of functions to every role (lo_from_bytea writes, pg_advisory_lock
# holds pooled connections, repeat('a', 1e9) exhausts memory), and a denylist
# will always miss one. These are the aggregate, date, string and window
# functions an investigation query actually needs. Names are sqlglot's
# canonical ones (e.g. string_agg parses as group_concat).
ALLOWED_FUNCTIONS = frozenset({
    # aggregates
    "count", "sum", "avg", "min", "max", "array_agg", "group_concat", "j_s_o_n_array_agg",
    "logical_or", "logical_and", "bool_or", "bool_and",
    # conditionals
    "coalesce", "nullif", "greatest", "least", "if", "case",
    # math
    "abs", "round", "ceil", "floor",
    # strings
    "lower", "upper", "length", "concat", "trim", "substring", "str_position", "replace",
    "left", "right", "initcap", "split_part",
    # dates
    "current_date", "current_timestamp", "extract", "timestamp_trunc", "date_trunc",
    "time_to_str", "to_char", "date_part", "age", "cast", "try_cast",
    # windows
    "row_number", "rank", "dense_rank", "lag", "lead", "first_value", "last_value",
    # json output shaping
    "json_build_object", "jsonb_build_object", "json_object",
})

# Operator nodes that sqlglot models as Func subclasses.
_OPERATORS = (exp.Binary, exp.Connector, exp.Predicate, exp.Unary, exp.In, exp.Between, exp.Case, exp.If)

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
    # TokenError (e.g. an unterminated string) is not a ParseError subclass;
    # uncaught, it crashed the run instead of going back to the model.
    except (sqlglot.errors.ParseError, sqlglot.errors.TokenError) as e:
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
        if isinstance(func, _OPERATORS):
            continue  # AND/OR/IN/=/+ are Func subclasses in sqlglot, not calls
        fname = (func.name if isinstance(func, exp.Anonymous) else func.sql_name()).lower()
        if fname not in ALLOWED_FUNCTIONS:
            return _reject(f"function '{fname}' is not allowed")

    # Casts to OID types (::regclass, ::regproc) resolve arbitrary catalog
    # objects. Check the bare type name so `pg_catalog.regclass` can't slip
    # past, and refuse schema-qualified types outright: none are needed.
    for cast in tree.find_all(exp.Cast):
        type_sql = cast.to.sql().lower()
        if "." in type_sql or type_sql.strip('"').startswith("reg"):
            return _reject(f"cast to {cast.to.sql()} is not allowed")

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
