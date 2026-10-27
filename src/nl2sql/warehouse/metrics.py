"""Metric definitions shared by the prompt, the schema endpoint, and the docs."""

from __future__ import annotations

METRICS: list[dict[str, str]] = [
    {
        "name": "net_sales",
        "definition": (
            "SUM(fact_order_line.net_amount_cents) / 100.0 where status = 'completed'. "
            "Cancelled, returned, and pending lines are excluded."
        ),
    },
    {
        "name": "revenue",
        "definition": "Same as net_sales unless the question explicitly says gross.",
    },
    {
        "name": "orders",
        "definition": (
            "COUNT(DISTINCT fact_order_line.order_id). The fact grain is one row per "
            "order line, so line counts and order counts differ when an order has several lines."
        ),
    },
    {
        "name": "average_order_value",
        "definition": (
            "Completed net sales divided by COUNT(DISTINCT order_id), usually by channel. "
            "A multi-line order counts once."
        ),
    },
    {
        "name": "returned_quantity",
        "definition": "SUM(quantity) where status = 'returned'.",
    },
    {
        "name": "new_customers",
        "definition": (
            "COUNT of dim_customer rows whose signup_date falls in the requested window. "
            "This does not require an order."
        ),
    },
]


def glossary_text() -> str:
    """Plain-text glossary embedded in the schema-aware model prompt."""
    lines = ["Metric glossary:"]
    for metric in METRICS:
        lines.append(f"- {metric['name']}: {metric['definition']}")
    lines.append(
        "Money is stored as integer cents. Sum net_amount_cents (or gross_amount_cents) "
        "first, then divide by 100.0. v_order_line.net_amount is rounded for display; "
        "do not sum it when the total must tie out to cents."
    )
    lines.append(
        "discount_bps is basis points of the line discount: 1000 means 10 percent, "
        "10000 means 100 percent. gross_amount_cents = quantity * unit_price_cents."
    )
    lines.append(
        "dim_date covers every calendar day from 2022-01-01 through 2025-12-31. "
        "Join fact_order_line.date_key to dim_date.date_key. "
        "Customer signup_date is an ISO date string on dim_customer."
    )
    return "\n".join(lines)
