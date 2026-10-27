"""The safety gate rejects writes and caps rows before SQLite sees the text."""

from __future__ import annotations

import pytest

from nl2sql.errors import UnsafeSQLError
from nl2sql.sql.safety import apply_row_limit, prepare_sql, validate_select


def test_allows_select() -> None:
    sql = validate_select("SELECT region FROM dim_customer")
    assert "dim_customer" in sql.lower()
    assert "select" in sql.lower()


def test_allows_cte() -> None:
    sql = validate_select("WITH c AS (SELECT 1 AS n) SELECT n FROM c")
    assert "with" in sql.lower()


def test_allows_union() -> None:
    sql = validate_select("SELECT 1 AS n UNION ALL SELECT 2")
    assert "union" in sql.lower()


def test_allows_string_that_mentions_drop() -> None:
    sql = validate_select("SELECT 'DROP TABLE dim_customer' AS label")
    assert "DROP TABLE" in sql


@pytest.mark.parametrize(
    ("statement", "token"),
    [
        ("DROP TABLE dim_customer", "DROP"),
        ("DELETE FROM dim_customer", "DELETE"),
        ("UPDATE dim_customer SET city = 'x'", "UPDATE"),
        ("INSERT INTO dim_customer (customer_id) VALUES (1)", "INSERT"),
        ("ALTER TABLE dim_customer ADD COLUMN x INT", "ALTER"),
        ("CREATE TABLE pwn (id INT)", "CREATE"),
        ("REPLACE INTO dim_customer (customer_id) VALUES (1)", "Command"),
        ("PRAGMA query_only = OFF", "PRAGMA"),
        ("ATTACH DATABASE 'other.db' AS other", "ATTACH"),
        ("VACUUM", "Command"),
    ],
)
def test_rejects_writes_and_admin_commands(statement: str, token: str) -> None:
    with pytest.raises(UnsafeSQLError) as caught:
        validate_select(statement)
    assert caught.value.reason in {"forbidden_statement", "not_select"}
    assert token.lower() in str(caught.value).lower() or token.lower() in caught.value.reason


def test_rejects_multiple_statements() -> None:
    with pytest.raises(UnsafeSQLError) as caught:
        validate_select("SELECT 1; DELETE FROM dim_customer")
    assert caught.value.reason == "multiple_statements"


def test_rejects_drop_hidden_after_comment() -> None:
    statement = "SELECT 1; -- keep going\nDROP TABLE dim_customer"
    with pytest.raises(UnsafeSQLError) as caught:
        validate_select(statement)
    assert caught.value.reason == "multiple_statements"


def test_rejects_cte_that_deletes() -> None:
    with pytest.raises(UnsafeSQLError) as caught:
        validate_select("WITH c AS (SELECT 1 AS n) DELETE FROM dim_customer")
    assert "DELETE" in str(caught.value)


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT load_extension('evil.so')",
        "SELECT writefile('/tmp/owned', 'x')",
        "SELECT readfile('/etc/passwd')",
    ],
)
def test_rejects_side_effect_functions(statement: str) -> None:
    with pytest.raises(UnsafeSQLError) as caught:
        validate_select(statement)
    assert caught.value.reason == "forbidden_function"


def test_rejects_empty_and_whitespace() -> None:
    with pytest.raises(UnsafeSQLError) as caught:
        validate_select("   ")
    assert caught.value.reason == "empty"


def test_adds_limit_when_missing() -> None:
    sql, capped = apply_row_limit(validate_select("SELECT 1 AS n"), 25)
    assert capped is True
    assert "limit 25" in sql.lower()


def test_keeps_tighter_limit() -> None:
    sql, capped = apply_row_limit(validate_select("SELECT 1 AS n LIMIT 5"), 25)
    assert capped is False
    assert "limit 5" in sql.lower()


def test_lowers_excessive_limit() -> None:
    sql, capped = apply_row_limit(validate_select("SELECT 1 AS n LIMIT 100000"), 25)
    assert capped is True
    assert "limit 25" in sql.lower()
    assert "100000" not in sql


def test_negative_limit_is_not_a_bypass() -> None:
    sql, capped = prepare_sql("SELECT full_date FROM dim_date LIMIT -1", 10)
    compact = "".join(sql.lower().split())
    assert capped is True
    assert "limit10" in compact
    assert "limit-1" not in compact


def test_rendered_sql_has_a_single_statement() -> None:
    sql = validate_select("/* noise */ SELECT 1 AS n;   ")
    assert sql.lower().count("select") == 1
    again = validate_select(sql)
    assert "select" in again.lower()
