"""Seed integrity: grain, keys, cents, and the documented population."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from nl2sql.warehouse.seed import (
    CUSTOMERS,
    DATE_END,
    DATE_START,
    ORDER_LINES,
    PRODUCTS,
    line_amounts,
)


def test_line_amounts_use_half_up_cents() -> None:
    assert line_amounts(2, 79_900, 1000) == (159_800, 143_820)
    assert line_amounts(4, 79_900, 1000) == (319_600, 287_640)


def test_population_counts(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        assert _scalar(connection, "SELECT COUNT(*) FROM dim_customer") == len(CUSTOMERS) == 12
        assert _scalar(connection, "SELECT COUNT(*) FROM dim_product") == len(PRODUCTS) == 10
        assert _scalar(connection, "SELECT COUNT(*) FROM fact_order_line") == len(ORDER_LINES) == 34
        assert _scalar(connection, "SELECT COUNT(*) FROM dim_date") == 1461
        bounds = connection.execute("SELECT MIN(full_date), MAX(full_date) FROM dim_date").fetchone()
        assert bounds == (DATE_START.isoformat(), DATE_END.isoformat())
    finally:
        connection.close()


def test_foreign_keys_and_money_formula(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        rows = connection.execute(
            """
            SELECT quantity, unit_price_cents, discount_bps, gross_amount_cents, net_amount_cents
            FROM fact_order_line
            """
        )
        for quantity, price, discount, gross, net in rows:
            expected_gross, expected_net = line_amounts(quantity, price, discount)
            assert gross == expected_gross
            assert net == expected_net
    finally:
        connection.close()


def test_multiline_order_makes_grain_visible(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        orders, lines = connection.execute(
            """
            SELECT COUNT(DISTINCT order_id), COUNT(*)
            FROM fact_order_line
            WHERE order_id = 40
            """
        ).fetchone()
        assert orders == 1
        assert lines == 2
    finally:
        connection.close()


def test_signups_in_2024_are_five(db_path: Path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        assert _scalar(
            connection,
            """
            SELECT COUNT(*) FROM dim_customer
            WHERE signup_date >= '2024-01-01' AND signup_date < '2025-01-01'
            """,
        ) == 5
    finally:
        connection.close()


def _scalar(connection: sqlite3.Connection, sql: str) -> int:
    row = connection.execute(sql).fetchone()
    assert row is not None
    return int(row[0])
