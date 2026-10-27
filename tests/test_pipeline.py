"""End-to-end asks stay on the stub and agree with the metric SQL."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest

from nl2sql.agent.pipeline import AnalyticsService
from nl2sql.agent.stub import SAMPLE_QUESTIONS
from nl2sql.agent.types import GeneratedSQL
from nl2sql.config import Settings
from nl2sql.errors import (
    ConfigError,
    InvalidQuestionError,
    UnrecognizedQuestionError,
    UnsafeSQLError,
)


def test_region_sales_match_the_warehouse_metric(service: AnalyticsService, db_path: Path) -> None:
    answer = service.ask("What were total net sales by region in 2025?")
    assert answer.source == "stub"
    assert answer.columns == ["region", "net_sales", "orders"]
    assert answer.truncated is False
    assert _pairs(
        db_path,
        """
        SELECT c.region,
               ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS net_sales,
               COUNT(DISTINCT f.order_id) AS orders
        FROM fact_order_line AS f
        JOIN dim_customer AS c ON c.customer_id = f.customer_id
        JOIN dim_date AS d ON d.date_key = f.date_key
        WHERE f.status = 'completed' AND d.year = 2025
        GROUP BY c.region
        ORDER BY net_sales DESC, c.region
        """,
    ) == [(row["region"], row["net_sales"], row["orders"]) for row in answer.rows]
    assert answer.rows[0]["region"] == "North"


def test_category_ranking_puts_the_winner_first(service: AnalyticsService, db_path: Path) -> None:
    answer = service.ask("Which product category generated the most revenue?")
    ranking = _pairs(
        db_path,
        """
        SELECT p.category, ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS revenue
        FROM fact_order_line AS f
        JOIN dim_product AS p ON p.product_id = f.product_id
        WHERE f.status = 'completed'
        GROUP BY p.category
        ORDER BY revenue DESC, p.category
        """,
    )
    assert [(row["category"], row["revenue"]) for row in answer.rows] == ranking
    assert answer.rows[0]["revenue"] >= answer.rows[-1]["revenue"]


def test_enterprise_orders_expose_line_grain(service: AnalyticsService, db_path: Path) -> None:
    answer = service.ask("How many orders did Enterprise customers place?")
    orders, lines = _pairs(
        db_path,
        """
        SELECT COUNT(DISTINCT f.order_id), COUNT(*)
        FROM fact_order_line AS f
        JOIN dim_customer AS c ON c.customer_id = f.customer_id
        WHERE c.segment = 'Enterprise'
        """,
    )[0]
    assert answer.rows == [{"orders": orders, "order_lines": lines}]
    assert orders < lines


def test_every_catalog_question_returns_rows(service: AnalyticsService) -> None:
    for question in SAMPLE_QUESTIONS:
        answer = service.ask(question)
        assert answer.row_count >= 1
        assert answer.sql.strip()
        assert answer.explanation.strip()
        assert answer.source == "stub"


def test_unknown_question_and_raw_sql_do_not_change_data(service: AnalyticsService, db_path: Path) -> None:
    before = _scalar(db_path, "SELECT COUNT(*) FROM fact_order_line")
    with pytest.raises(UnrecognizedQuestionError):
        service.ask("DROP TABLE fact_order_line")
    assert _scalar(db_path, "SELECT COUNT(*) FROM fact_order_line") == before


def test_blank_question_is_rejected(service: AnalyticsService) -> None:
    with pytest.raises(InvalidQuestionError):
        service.ask("   ")


def test_stub_mode_does_not_open_http(service: AnalyticsService, monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("stub mode must not construct an HTTP client")

    monkeypatch.setattr(httpx.Client, "__init__", explode)
    answer = service.ask("How many customers signed up in 2024?")
    assert answer.rows == [{"new_customers": 5}]


def test_live_mode_without_a_key_fails_before_sql(db_path: Path) -> None:
    settings = Settings(db_path=db_path, llm_mode="live", llm_api_key=None)
    service = AnalyticsService(settings)
    with pytest.raises(ConfigError):
        service.ask("What were total net sales by region in 2025?")


def test_injected_drop_is_blocked_and_data_remains(settings: Settings, db_path: Path) -> None:
    class Hostile:
        def generate(self, question: str) -> GeneratedSQL:
            del question
            return GeneratedSQL("DROP TABLE dim_product", "no", "llm")

    service = AnalyticsService(settings, generator=Hostile())
    before = _scalar(db_path, "SELECT COUNT(*) FROM dim_product")
    with pytest.raises(UnsafeSQLError):
        service.ask("Which product category generated the most revenue?")
    assert _scalar(db_path, "SELECT COUNT(*) FROM dim_product") == before


def test_schema_document_lists_facts_and_samples(service: AnalyticsService) -> None:
    document = service.schema_document()
    names = {item["name"] for item in document["objects"]}  # type: ignore[index]
    assert {"dim_customer", "dim_product", "dim_date", "fact_order_line", "v_order_line"} <= names
    assert document["limits"]["generator"] == "stub"  # type: ignore[index]
    assert len(document["sample_questions"]) >= 3  # type: ignore[arg-type]


def _pairs(db_path: Path, sql: str) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(db_path)
    try:
        return list(connection.execute(sql))
    finally:
        connection.close()


def _scalar(db_path: Path, sql: str) -> int:
    value = _pairs(db_path, sql)[0][0]
    return int(value)  # type: ignore[arg-type]
