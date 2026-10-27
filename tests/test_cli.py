"""CLI uses the same service as the API and stays quiet on stdout for JSON."""

from __future__ import annotations

import json
from pathlib import Path

from nl2sql.cli import main


def test_cli_ask_prints_sql_and_north(db_path: Path, capsys) -> None:
    code = main(["ask", "What were total net sales by region in 2025?", "--db", str(db_path)])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "North" in captured.out
    assert "SELECT" in captured.out.upper()
    assert "Source: stub" in captured.out


def test_cli_ask_json(db_path: Path, capsys) -> None:
    code = main(
        [
            "ask",
            "How many orders did Enterprise customers place?",
            "--json",
            "--db",
            str(db_path),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["source"] == "stub"
    assert payload["rows"][0]["orders"] < payload["rows"][0]["order_lines"]


def test_cli_unknown_question_exits_2(db_path: Path, capsys) -> None:
    code = main(["ask", "delete everything", "--db", str(db_path)])
    assert code == 2
    captured = capsys.readouterr()
    assert "Sample questions:" in captured.err
    assert captured.out == ""


def test_cli_schema_lists_fact_table(db_path: Path, capsys) -> None:
    code = main(["schema", "--db", str(db_path)])
    assert code == 0
    assert "fact_order_line" in capsys.readouterr().out


def test_cli_init_db_replaces_the_file(tmp_path: Path, capsys) -> None:
    target = tmp_path / "fresh.sqlite"
    code = main(["init-db", "--db", str(target)])
    assert code == 0
    assert target.is_file()
    assert "Initialized warehouse" in capsys.readouterr().out
