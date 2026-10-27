"""Deterministic seed for the demo warehouse.

Amounts are computed in integer cents so tests can reconcile the fact table
without floating-point drift. discount_bps is the line discount in basis points.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCHEMA_SQL = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")

DATE_START = date(2022, 1, 1)
DATE_END = date(2025, 12, 31)

# customer_id, name, email, segment, region, country, city, signup_date
CUSTOMERS: tuple[tuple[object, ...], ...] = (
    (1, "Northwind Labs", "northwind@example.com", "Enterprise", "North", "USA", "Chicago", "2023-03-12"),
    (2, "Brightpath Retail", "brightpath@example.com", "Mid-Market", "South", "USA", "Austin", "2024-01-15"),
    (3, "Helios Manufacturing", "helios@example.com", "Enterprise", "West", "USA", "Denver", "2022-11-02"),
    (4, "Cobalt Finance", "cobalt@example.com", "Enterprise", "East", "USA", "Boston", "2023-06-20"),
    (5, "Lumen Health", "lumen@example.com", "Mid-Market", "North", "USA", "Minneapolis", "2024-06-01"),
    (6, "Orbit Logistics", "orbit@example.com", "SMB", "West", "USA", "Phoenix", "2024-09-18"),
    (7, "Maple & Co", "maple@example.com", "SMB", "North", "Canada", "Toronto", "2024-02-11"),
    (8, "Danube Analytics", "danube@example.com", "Mid-Market", "EU", "Germany", "Berlin", "2023-12-01"),
    (9, "Sierra Outdoor", "sierra@example.com", "SMB", "South", "USA", "Atlanta", "2025-01-09"),
    (10, "Pinnacle Media", "pinnacle@example.com", "Enterprise", "East", "USA", "New York", "2022-08-30"),
    (11, "Harbor Foods", "harbor@example.com", "Mid-Market", "South", "USA", "Miami", "2025-03-22"),
    (12, "Alpine Software", "alpine@example.com", "SMB", "EU", "Switzerland", "Zurich", "2024-11-05"),
)

# product_id, sku, name, category, subcategory, list_price_cents
PRODUCTS: tuple[tuple[object, ...], ...] = (
    (1, "HW-LAP-14", "Fieldbook Laptop 14", "Hardware", "Laptops", 129_900),
    (2, "HW-MON-27", "Clarity Monitor 27", "Hardware", "Displays", 44_900),
    (3, "HW-KEY-01", "QuietType Keyboard", "Hardware", "Accessories", 8_900),
    (4, "SW-ANL-PRO", "Insight Analytics Pro", "Software", "Analytics", 19_900),
    (5, "SW-ANL-ENT", "Insight Analytics Enterprise", "Software", "Analytics", 79_900),
    (6, "SW-VIS-01", "Chartline Studio", "Software", "Visualization", 4_900),
    (7, "SV-ONB-01", "Onboarding Package", "Services", "Onboarding", 150_000),
    (8, "SV-SUP-GLD", "Gold Support (annual)", "Services", "Support", 99_900),
    (9, "SW-ETL-01", "Pipeline Runner", "Software", "Data Engineering", 29_900),
    (10, "HW-DOC-01", "Dock Station Pro", "Hardware", "Accessories", 17_900),
)

# order_id, order_line_id, customer_id, product_id, order_date, qty, unit_price_cents,
# discount_bps, status, channel
# Order 40 has two lines so COUNT(*) and COUNT(DISTINCT order_id) disagree.
ORDER_LINES: tuple[tuple[object, ...], ...] = (
    (1, 1, 1, 5, "2024-01-15", 2, 79_900, 1000, "completed", "direct"),
    (2, 2, 2, 4, "2024-02-02", 5, 19_900, 0, "completed", "web"),
    (3, 3, 3, 1, "2024-03-10", 3, 129_900, 500, "completed", "direct"),
    (4, 4, 4, 8, "2024-04-05", 1, 99_900, 0, "completed", "partner"),
    (5, 5, 7, 6, "2024-05-20", 10, 4_900, 0, "completed", "web"),
    (6, 6, 8, 9, "2024-06-12", 2, 29_900, 1500, "completed", "web"),
    (7, 7, 6, 3, "2024-07-01", 4, 8_900, 0, "completed", "web"),
    (8, 8, 10, 7, "2024-08-18", 1, 150_000, 2000, "completed", "direct"),
    (9, 9, 5, 2, "2024-09-09", 2, 44_900, 0, "completed", "partner"),
    (10, 10, 12, 4, "2024-10-22", 1, 19_900, 0, "completed", "web"),
    (11, 11, 1, 5, "2024-11-11", 1, 79_900, 0, "completed", "direct"),
    (12, 12, 3, 10, "2024-12-02", 3, 17_900, 0, "returned", "web"),
    (13, 13, 1, 5, "2025-01-20", 4, 79_900, 1000, "completed", "direct"),
    (14, 14, 2, 1, "2025-02-14", 1, 129_900, 0, "completed", "web"),
    (15, 15, 9, 6, "2025-02-14", 20, 4_900, 500, "completed", "web"),
    (16, 16, 4, 8, "2025-03-03", 2, 99_900, 0, "completed", "partner"),
    (17, 17, 11, 2, "2025-03-18", 6, 44_900, 1000, "completed", "direct"),
    (18, 18, 8, 9, "2025-04-07", 3, 29_900, 0, "completed", "web"),
    (19, 19, 10, 7, "2025-04-21", 1, 150_000, 0, "completed", "direct"),
    (20, 20, 3, 1, "2025-05-05", 2, 129_900, 500, "completed", "direct"),
    (21, 21, 5, 4, "2025-06-16", 8, 19_900, 0, "completed", "web"),
    (22, 22, 6, 3, "2025-07-09", 2, 8_900, 0, "cancelled", "web"),
    (23, 23, 12, 10, "2025-07-28", 2, 17_900, 0, "completed", "partner"),
    (24, 24, 1, 8, "2025-08-15", 1, 99_900, 0, "completed", "direct"),
    (25, 25, 7, 6, "2025-09-02", 15, 4_900, 0, "completed", "web"),
    (26, 26, 4, 5, "2025-09-30", 2, 79_900, 1000, "completed", "partner"),
    (27, 27, 2, 9, "2025-10-11", 1, 29_900, 0, "completed", "web"),
    (28, 28, 10, 2, "2025-11-04", 4, 44_900, 0, "pending", "direct"),
    (29, 29, 11, 4, "2025-11-19", 3, 19_900, 0, "completed", "web"),
    (30, 30, 3, 7, "2025-12-08", 1, 150_000, 1000, "completed", "direct"),
    (31, 31, 9, 3, "2025-01-08", 1, 8_900, 0, "returned", "web"),
    (32, 32, 5, 10, "2025-03-25", 5, 17_900, 0, "completed", "partner"),
    (40, 40, 1, 3, "2025-06-02", 2, 8_900, 0, "completed", "direct"),
    (40, 41, 1, 10, "2025-06-02", 1, 17_900, 0, "completed", "direct"),
)


def line_amounts(quantity: int, unit_price_cents: int, discount_bps: int) -> tuple[int, int]:
    """Return (gross_cents, net_cents) using half-up rounding to the cent."""
    gross = quantity * unit_price_cents
    net = (
        Decimal(gross) * (Decimal(10_000) - Decimal(discount_bps)) / Decimal(10_000)
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return gross, int(net)


def date_key_for(iso_day: str) -> int:
    parsed = date.fromisoformat(iso_day)
    return int(parsed.strftime("%Y%m%d"))


def build_database(path: Path) -> Path:
    """Create a fresh warehouse at `path`, replacing any previous file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)
        connection.execute("PRAGMA foreign_keys = ON")
        _insert_dates(connection)
        connection.executemany(
            """
            INSERT INTO dim_customer (
                customer_id, customer_name, email, segment, region, country, city, signup_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            CUSTOMERS,
        )
        connection.executemany(
            """
            INSERT INTO dim_product (
                product_id, sku, product_name, category, subcategory, list_price_cents
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            PRODUCTS,
        )
        fact_rows = []
        for (
            order_id,
            order_line_id,
            customer_id,
            product_id,
            order_date,
            quantity,
            unit_price_cents,
            discount_bps,
            status,
            channel,
        ) in ORDER_LINES:
            gross, net = line_amounts(int(quantity), int(unit_price_cents), int(discount_bps))
            fact_rows.append(
                (
                    order_line_id,
                    order_id,
                    customer_id,
                    product_id,
                    date_key_for(str(order_date)),
                    quantity,
                    unit_price_cents,
                    discount_bps,
                    gross,
                    net,
                    status,
                    channel,
                )
            )
        connection.executemany(
            """
            INSERT INTO fact_order_line (
                order_line_id, order_id, customer_id, product_id, date_key,
                quantity, unit_price_cents, discount_bps, gross_amount_cents,
                net_amount_cents, status, channel
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            fact_rows,
        )
        connection.commit()
    except Exception:
        connection.close()
        if temporary.exists():
            temporary.unlink()
        raise
    connection.close()
    temporary.replace(path)
    return path


def ensure_database(path: Path) -> Path:
    """Build the warehouse when the file is missing or empty."""
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        return path
    return build_database(path)


def _insert_dates(connection: sqlite3.Connection) -> None:
    rows = []
    current = DATE_START
    while current <= DATE_END:
        rows.append(
            (
                int(current.strftime("%Y%m%d")),
                current.isoformat(),
                current.year,
                (current.month - 1) // 3 + 1,
                current.month,
                current.strftime("%B"),
                current.day,
                current.strftime("%A"),
                1 if current.weekday() >= 5 else 0,
            )
        )
        current += timedelta(days=1)
    connection.executemany(
        """
        INSERT INTO dim_date (
            date_key, full_date, year, quarter, month, month_name, day, day_name, is_weekend
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
