"""Command-line entry point for the same ask flow the API uses."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from nl2sql.agent.pipeline import AnalyticsService
from nl2sql.agent.types import AskAnswer
from nl2sql.config import Settings
from nl2sql.errors import NL2SQLError, QueryTimeoutError, UnrecognizedQuestionError, UnsafeSQLError
from nl2sql.warehouse.seed import build_database


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except UnrecognizedQuestionError as exc:
        print(str(exc), file=sys.stderr)
        print("Sample questions:", file=sys.stderr)
        for question in exc.sample_questions:
            print(f"  - {question}", file=sys.stderr)
        return 2
    except UnsafeSQLError as exc:
        print(f"Unsafe SQL ({exc.reason}): {exc}", file=sys.stderr)
        return 3
    except QueryTimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except NL2SQLError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--db", help="Path to the SQLite warehouse file")

    parser = argparse.ArgumentParser(
        prog="nl2sql",
        description="Ask a natural-language question of the demo analytics warehouse.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", parents=[common], help="Answer one question")
    ask.add_argument("question", help="Natural-language question")
    ask.add_argument("--json", action="store_true", help="Print the API-shaped JSON object")
    ask.set_defaults(handler=_ask)

    schema = subparsers.add_parser("schema", parents=[common], help="Print the live catalog")
    schema.add_argument("--json", action="store_true", help="Print the schema document as JSON")
    schema.set_defaults(handler=_schema)

    init_db = subparsers.add_parser(
        "init-db",
        parents=[common],
        help="Create or replace the seeded warehouse",
    )
    init_db.set_defaults(handler=_init_db)

    serve = subparsers.add_parser("serve", parents=[common], help="Run the HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(handler=_serve)
    return parser


def _settings_from_args(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    if args.db:
        settings = replace(settings, db_path=Path(args.db))
    return settings


def _ask(args: argparse.Namespace) -> int:
    answer = AnalyticsService(_settings_from_args(args)).ask(args.question)
    if args.json:
        json.dump(answer.as_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_answer(answer)
    return 0


def _schema(args: argparse.Namespace) -> int:
    document = AnalyticsService(_settings_from_args(args)).schema_document()
    if args.json:
        json.dump(document, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    objects = document["objects"]
    if isinstance(objects, list):
        for item in objects:
            if not isinstance(item, dict):
                continue
            print(f"{item['type']:5} {item['name']}")
            columns = item.get("columns")
            if isinstance(columns, list):
                for column in columns:
                    if isinstance(column, dict):
                        print(f"  - {column['name']} {column['type']}")
    print("\nSample questions:")
    questions = document["sample_questions"]
    if isinstance(questions, list):
        for question in questions:
            print(f"  - {question}")
    return 0


def _init_db(args: argparse.Namespace) -> int:
    path = build_database(_settings_from_args(args).db_path)
    print(f"Initialized warehouse at {path}")
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    from nl2sql.api.app import create_app

    uvicorn.run(create_app(_settings_from_args(args)), host=args.host, port=args.port)
    return 0


def _print_answer(answer: AskAnswer) -> None:
    print(f"Source: {answer.source}")
    print("\nSQL:")
    print(answer.sql)
    print("\nExplanation:")
    print(answer.explanation)
    print()
    if not answer.rows:
        print("(no rows)")
    else:
        print(_format_table(answer.columns, answer.rows))
    suffix = " (row cap reached; more rows may exist)" if answer.truncated else ""
    label = "row" if answer.row_count == 1 else "rows"
    print(f"\n{answer.row_count} {label}{suffix}")


def _format_table(columns: list[str], rows: list[dict[str, object]]) -> str:
    rendered = [[_cell(row.get(column)) for column in columns] for row in rows]
    widths = [len(column) for column in columns]
    for cells in rendered:
        for index, cell in enumerate(cells):
            widths[index] = min(48, max(widths[index], len(cell)))

    def clip(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        return text[: width - 3] + "..."

    header = "  ".join(clip(column, widths[index]).ljust(widths[index]) for index, column in enumerate(columns))
    rule = "  ".join("-" * width for width in widths)
    body = [
        "  ".join(clip(cell, widths[index]).ljust(widths[index]) for index, cell in enumerate(cells))
        for cells in rendered
    ]
    return "\n".join([header, rule, *body])


def _cell(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
