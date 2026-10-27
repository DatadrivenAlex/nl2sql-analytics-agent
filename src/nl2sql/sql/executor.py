"""Execute prepared SELECT statements on a read-only SQLite connection."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nl2sql.errors import QueryExecutionError, QueryTimeoutError, UnsafeSQLError
from nl2sql.sql.safety import prepare_sql

# SQLite authorizer action codes. Kept local so a missing constant fails closed.
_SQLITE_OK = sqlite3.SQLITE_OK
_SQLITE_DENY = sqlite3.SQLITE_DENY
_ALLOWED_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_RECURSIVE,
    }
)
_FORBIDDEN_FUNCTIONS = frozenset(
    {"load_extension", "writefile", "readfile", "edit", "fts3_tokenizer"}
)


@dataclass(frozen=True)
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool


class Executor:
    """Run one capped SELECT against the demo warehouse."""

    def __init__(self, db_path: Path, max_rows: int, timeout_s: float) -> None:
        self.db_path = Path(db_path)
        self.max_rows = max_rows
        self.timeout_s = timeout_s

    def execute(self, sql: str) -> QueryResult:
        safe_sql, capped = prepare_sql(sql, self.max_rows)
        connection = _connect(self.db_path)
        deadline = time.monotonic() + self.timeout_s

        def _progress() -> int:
            if time.monotonic() >= deadline:
                return 1
            return 0

        connection.set_authorizer(_authorizer)
        connection.set_progress_handler(_progress, 10_000)
        try:
            try:
                cursor = connection.execute(safe_sql)
            except sqlite3.Error as exc:
                _raise_sqlite(exc, self.timeout_s)
            if cursor.description is None:
                raise QueryExecutionError("Statement did not return a result set")
            columns = [str(item[0]) for item in cursor.description]
            materialised = [dict(row) for row in cursor.fetchall()]
        finally:
            connection.close()
        truncated = capped and len(materialised) >= self.max_rows
        return QueryResult(
            sql=safe_sql,
            columns=columns,
            rows=materialised,
            row_count=len(materialised),
            truncated=truncated,
        )


def _connect(path: Path) -> sqlite3.Connection:
    resolved = Path(path).expanduser().resolve()
    uri = f"file:{resolved.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    # Set before the authorizer. The authorizer denies later PRAGMA statements.
    connection.execute("PRAGMA query_only = ON")
    return connection


def _authorizer(action: int, arg1: str | None, arg2: str | None, db_name: str | None, source: str | None) -> int:
    del db_name, source
    if action == sqlite3.SQLITE_FUNCTION:
        names = {str(arg1 or "").lower(), str(arg2 or "").lower()}
        if names & _FORBIDDEN_FUNCTIONS:
            return _SQLITE_DENY
        return _SQLITE_OK
    if action in _ALLOWED_ACTIONS:
        return _SQLITE_OK
    return _SQLITE_DENY


def _raise_sqlite(exc: sqlite3.Error, timeout_s: float) -> None:
    text = str(exc).lower()
    if "interrupted" in text:
        raise QueryTimeoutError(f"Query exceeded {timeout_s:g} seconds") from exc
    if "not authorized" in text:
        raise UnsafeSQLError(
            "SQLite refused the statement (read-only authorizer)",
            "authorizer",
        ) from exc
    raise QueryExecutionError(str(exc)) from exc
