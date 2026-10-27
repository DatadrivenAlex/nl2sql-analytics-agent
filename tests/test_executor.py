"""Execution stays read-only even if a caller skips a polite API."""

from __future__ import annotations

import sqlite3

import pytest

from nl2sql.errors import QueryTimeoutError, UnsafeSQLError
from nl2sql.sql.executor import Executor, _authorizer
from nl2sql.warehouse.db import connect_readonly


def test_select_returns_column_dicts(executor: Executor) -> None:
    result = executor.execute(
        "SELECT segment, COUNT(*) AS customers FROM dim_customer GROUP BY segment ORDER BY segment"
    )
    assert result.columns == ["segment", "customers"]
    assert result.row_count == 3
    assert sum(row["customers"] for row in result.rows) == 12
    assert result.truncated is False


def test_negative_limit_returns_only_the_cap(db_path) -> None:
    executor = Executor(db_path, max_rows=5, timeout_s=5)
    result = executor.execute("SELECT full_date FROM dim_date ORDER BY full_date LIMIT -1")
    assert result.row_count == 5
    assert result.truncated is True
    assert "limit 5" in result.sql.lower()


def test_question_like_delete_does_not_run_as_sql(executor: Executor, db_path) -> None:
    before = _count(db_path, "SELECT COUNT(*) FROM dim_customer")
    with pytest.raises(UnsafeSQLError):
        executor.execute("DELETE FROM dim_customer")
    with pytest.raises(UnsafeSQLError):
        executor.execute("SELECT customer_name FROM dim_customer; DELETE FROM dim_customer")
    assert _count(db_path, "SELECT COUNT(*) FROM dim_customer") == before


def test_readonly_connection_rejects_insert(db_path) -> None:
    connection = connect_readonly(db_path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute(
                """
                INSERT INTO dim_customer (
                    customer_id, customer_name, email, segment, region, country, city, signup_date
                ) VALUES (99, 'Nope', 'nope@example.com', 'SMB', 'North', 'USA', 'X', '2024-01-01')
                """
            )
    finally:
        connection.close()


def test_timeout_interrupts_a_cartesian_product(db_path) -> None:
    executor = Executor(db_path, max_rows=10, timeout_s=0.05)
    with pytest.raises(QueryTimeoutError):
        executor.execute("SELECT COUNT(*) AS n FROM dim_date AS a, dim_date AS b, dim_date AS c")


def test_authorizer_denies_writes_and_load_extension() -> None:
    assert _authorizer(sqlite3.SQLITE_SELECT, None, None, None, None) == sqlite3.SQLITE_OK
    assert _authorizer(sqlite3.SQLITE_READ, "dim_customer", "city", "main", None) == sqlite3.SQLITE_OK
    assert _authorizer(sqlite3.SQLITE_DELETE, "dim_customer", None, "main", None) == sqlite3.SQLITE_DENY
    assert _authorizer(sqlite3.SQLITE_INSERT, "dim_customer", None, "main", None) == sqlite3.SQLITE_DENY
    assert _authorizer(sqlite3.SQLITE_UPDATE, "dim_customer", "city", "main", None) == sqlite3.SQLITE_DENY
    assert _authorizer(sqlite3.SQLITE_PRAGMA, "query_only", None, None, None) == sqlite3.SQLITE_DENY
    assert _authorizer(sqlite3.SQLITE_ATTACH, "other", None, None, None) == sqlite3.SQLITE_DENY
    assert (
        _authorizer(sqlite3.SQLITE_FUNCTION, None, "load_extension", None, None) == sqlite3.SQLITE_DENY
    )
    assert _authorizer(sqlite3.SQLITE_FUNCTION, None, "upper", None, None) == sqlite3.SQLITE_OK


def _count(db_path, sql: str) -> int:
    connection = sqlite3.connect(db_path)
    try:
        value = connection.execute(sql).fetchone()
    finally:
        connection.close()
    assert value is not None
    return int(value[0])
