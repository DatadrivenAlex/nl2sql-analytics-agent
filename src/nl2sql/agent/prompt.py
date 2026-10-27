"""Schema-aware prompt used by the optional live model."""

from __future__ import annotations

from nl2sql.warehouse.metrics import glossary_text


def build_system_prompt(schema_ddl: str, max_rows: int) -> str:
    """Instructions plus the live DDL. The question itself is the user message."""
    return f"""You translate one business question into one SQLite query for the demo warehouse.

Return JSON only, with string keys "sql" and "explanation". Do not use markdown.

SQL rules:
- One read-only statement. WITH ... SELECT and UNION are allowed.
- Use only tables, views, and columns from the schema below.
- Never emit INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, ATTACH, PRAGMA, or a second statement.
- Never call load_extension, writefile, readfile, edit, or fts3_tokenizer.
- End with a non-negative integer LIMIT of at most {max_rows}.
- For currency totals, SUM the integer cents columns and then divide by 100.0.
- Round displayed currency to 2 decimal places.
- Follow the metric glossary. Do not invent a different definition of net sales or orders.

Schema (from the live database):
{schema_ddl}

{glossary_text()}
"""
