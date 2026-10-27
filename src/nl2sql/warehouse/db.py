"""Read-only access and live catalog introspection."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from nl2sql.errors import WarehouseError

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def connect_readonly(path: Path) -> sqlite3.Connection:
    """Open SQLite in immutable-read mode. The file must already exist."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise WarehouseError(f"Warehouse database does not exist: {resolved.name}")
    uri = f"file:{resolved.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def introspect(path: Path) -> dict[str, object]:
    """Return tables, views, columns, and foreign keys from the live database."""
    connection = connect_readonly(path)
    try:
        objects = connection.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name
            """
        ).fetchall()
        catalog: list[dict[str, object]] = []
        for row in objects:
            name = str(row["name"])
            if _IDENTIFIER.fullmatch(name) is None:
                continue
            columns = [
                {
                    "name": column["name"],
                    "type": column["type"],
                    "not_null": bool(column["notnull"]),
                    "primary_key": bool(column["pk"]),
                }
                for column in connection.execute(f"PRAGMA table_info({name})")
            ]
            foreign_keys: list[dict[str, str]] = []
            if row["type"] == "table":
                foreign_keys = [
                    {
                        "from": fk["from"],
                        "to_table": fk["table"],
                        "to_column": fk["to"],
                    }
                    for fk in connection.execute(f"PRAGMA foreign_key_list({name})")
                ]
            catalog.append(
                {
                    "name": name,
                    "type": row["type"],
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "ddl": row["sql"],
                }
            )
        return {"dialect": "sqlite", "objects": catalog}
    finally:
        connection.close()


def render_ddl(path: Path) -> str:
    """DDL text for the schema-aware prompt, taken from sqlite_master."""
    snapshot = introspect(path)
    objects = snapshot["objects"]
    if not isinstance(objects, list) or not objects:
        raise WarehouseError("Warehouse catalog is empty")
    blocks: list[str] = []
    for item in objects:
        if not isinstance(item, dict):
            continue
        ddl = item.get("ddl")
        if isinstance(ddl, str) and ddl.strip():
            blocks.append(ddl.strip() + ";")
    return "\n\n".join(blocks)
