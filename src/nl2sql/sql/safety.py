"""Allow a single read-only query, then cap the rows it can return.

The string that later reaches SQLite is sqlglot's rendering of the parsed
statement, not the raw model text. A second statement hidden after a comment
or a semicolon never becomes part of that rendering.

SQLite treats a negative LIMIT as "no limit", so only a non-negative integer
literal at or below the configured cap is preserved. Anything else is replaced.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from nl2sql.errors import UnsafeSQLError

_QUERY_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery)

_FORBIDDEN_NAMES = (
    "Insert",
    "Update",
    "Delete",
    "Drop",
    "Alter",
    "Create",
    "Command",
    "Pragma",
    "Attach",
    "Detach",
    "Transaction",
    "Commit",
    "Rollback",
    "Merge",
    "Grant",
    "Revoke",
    "Analyze",
    "Copy",
    "Use",
    "Set",
)

_FORBIDDEN_TYPES = tuple(
    cls for name in _FORBIDDEN_NAMES if isinstance(cls := getattr(exp, name, None), type)
)

_FORBIDDEN_FUNCTIONS = frozenset(
    {
        "load_extension",
        "writefile",
        "readfile",
        "edit",
        "fts3_tokenizer",
    }
)

_MAX_SQL_CHARS = 10_000


def validate_select(sql: str) -> str:
    """Return a single rendered read-only statement, or raise UnsafeSQLError."""
    expression = _parse_single_query(sql)
    _reject_forbidden(expression)
    rendered = expression.sql(dialect="sqlite", pretty=True)
    confirmed = _parse_single_query(rendered)
    _reject_forbidden(confirmed)
    return confirmed.sql(dialect="sqlite", pretty=True)


def apply_row_limit(sql: str, max_rows: int) -> tuple[str, bool]:
    """Force LIMIT to a non-negative integer no larger than `max_rows`.

    Returns the rendered SQL and whether this function added or lowered the limit.
    """
    if max_rows < 1:
        raise UnsafeSQLError("Row cap must be a positive integer", "limit_invalid")
    try:
        expression = sqlglot.parse_one(sql, read="sqlite")
    except SqlglotError as exc:
        raise UnsafeSQLError("SQL could not be parsed", "parse_error") from exc
    if expression is None:
        raise UnsafeSQLError("SQL could not be parsed", "parse_error")
    current = _limit_value(expression.args.get("limit"))
    capped = current is None or current < 0 or current > max_rows
    if capped:
        expression.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return expression.sql(dialect="sqlite", pretty=True), capped


def prepare_sql(sql: str, max_rows: int) -> tuple[str, bool]:
    """Validate, then apply the row cap. This is the only SQL the executor runs."""
    return apply_row_limit(validate_select(sql), max_rows)


def _parse_single_query(sql: str) -> exp.Expression:
    text = sql.strip()
    if not text:
        raise UnsafeSQLError("SQL is empty", "empty")
    if len(text) > _MAX_SQL_CHARS:
        raise UnsafeSQLError("SQL exceeds the length cap", "too_long")
    try:
        statements = sqlglot.parse(text, read="sqlite")
    except SqlglotError as exc:
        raise UnsafeSQLError("SQL could not be parsed", "parse_error") from exc
    statements = [
        statement
        for statement in statements
        if statement is not None and not isinstance(statement, exp.Semicolon)
    ]
    if len(statements) != 1:
        raise UnsafeSQLError(
            "Only a single SELECT statement is allowed",
            "multiple_statements" if len(statements) > 1 else "empty",
        )
    expression = statements[0]
    # Name writes and admin commands before the generic "not a SELECT" check.
    _reject_forbidden(expression)
    if not isinstance(expression, _QUERY_ROOTS):
        raise UnsafeSQLError(
            "Only a single read-only SELECT query is allowed",
            "not_select",
        )
    return expression


def _reject_forbidden(expression: exp.Expression) -> None:
    for node in expression.walk():
        if isinstance(node, _FORBIDDEN_TYPES):
            raise UnsafeSQLError(
                f"{type(node).__name__.upper()} statements are not allowed",
                "forbidden_statement",
            )
        if isinstance(node, exp.Func):
            name = _function_name(node)
            if name in _FORBIDDEN_FUNCTIONS:
                raise UnsafeSQLError(
                    f"Function {name} is not allowed",
                    "forbidden_function",
                )


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return (node.name or "").lower()
    sql_name = getattr(node, "sql_name", None)
    if callable(sql_name):
        rendered = sql_name()
        if isinstance(rendered, str) and rendered.strip():
            return rendered.lower()
    return type(node).__name__.lower()


def _limit_value(limit: exp.Expression | None) -> int | None:
    if not isinstance(limit, exp.Limit):
        return None
    value = limit.expression
    if isinstance(value, exp.Neg):
        inner = value.this
        if isinstance(inner, exp.Literal) and inner.is_int:
            return -int(inner.this)
        return None
    if isinstance(value, exp.Literal) and value.is_int:
        return int(value.this)
    return None
