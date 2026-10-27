"""Deterministic SQL for a fixed catalog of demo questions.

This is not a model. Matching is exact after light normalization (case, punctuation,
and filler words). Unknown questions fail closed instead of inventing SQL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nl2sql.agent.types import GeneratedSQL
from nl2sql.errors import UnrecognizedQuestionError

_PUNCTUATION = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE = re.compile(r"\s+")
_FILLER = re.compile(r"\b(please|thanks|thank you)\b")


def normalize_question(question: str) -> str:
    text = question.lower().strip()
    text = _PUNCTUATION.sub(" ", text)
    text = _FILLER.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


@dataclass(frozen=True)
class DemoQuery:
    id: str
    question: str
    sql: str
    explanation: str
    aliases: tuple[str, ...] = ()


def _sql(body: str) -> str:
    return "\n".join(line.rstrip() for line in body.strip().splitlines())


QUERIES: tuple[DemoQuery, ...] = (
    DemoQuery(
        id="net_sales_by_region_2025",
        question="What were total net sales by region in 2025?",
        explanation=(
            "Net sales are completed order lines in 2025, summed in cents and divided "
            "by 100. Cancelled, returned, and pending lines are excluded. Region comes "
            "from the customer dimension."
        ),
        aliases=(
            "total net sales by region in 2025",
            "show net sales by region in 2025",
            "net sales by region for 2025",
        ),
        sql=_sql(
            """
            SELECT
              c.region,
              ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS net_sales,
              COUNT(DISTINCT f.order_id) AS orders
            FROM fact_order_line AS f
            JOIN dim_customer AS c ON c.customer_id = f.customer_id
            JOIN dim_date AS d ON d.date_key = f.date_key
            WHERE f.status = 'completed'
              AND d.year = 2025
            GROUP BY c.region
            ORDER BY net_sales DESC, c.region
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="top_category_by_revenue",
        question="Which product category generated the most revenue?",
        explanation=(
            "Ranks product categories by completed-line net sales across every year "
            "in the warehouse. The first row generated the most revenue. Revenue uses "
            "the net sales definition, not list price."
        ),
        aliases=(
            "which category generated the most revenue",
            "what product category generated the most revenue",
            "top product category by revenue",
        ),
        sql=_sql(
            """
            SELECT
              p.category,
              ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS revenue,
              SUM(f.quantity) AS units
            FROM fact_order_line AS f
            JOIN dim_product AS p ON p.product_id = f.product_id
            WHERE f.status = 'completed'
            GROUP BY p.category
            ORDER BY revenue DESC, p.category
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="enterprise_orders",
        question="How many orders did Enterprise customers place?",
        explanation=(
            "Counts orders placed by Enterprise customers in any status. "
            "fact_order_line is one row per order line, so orders and order_lines "
            "differ when an order contains more than one line."
        ),
        aliases=(
            "how many orders were placed by enterprise customers",
            "enterprise customer order count",
            "how many enterprise orders were placed",
        ),
        sql=_sql(
            """
            SELECT
              COUNT(DISTINCT f.order_id) AS orders,
              COUNT(*) AS order_lines
            FROM fact_order_line AS f
            JOIN dim_customer AS c ON c.customer_id = f.customer_id
            WHERE c.segment = 'Enterprise'
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="monthly_net_sales_2025",
        question="Show monthly net sales for 2025",
        explanation=(
            "Completed net sales for each month of 2025. Months with no completed "
            "lines are omitted rather than filled with zeros."
        ),
        aliases=(
            "monthly net sales for 2025",
            "what were monthly net sales in 2025",
            "show monthly revenue for 2025",
        ),
        sql=_sql(
            """
            SELECT
              d.month,
              d.month_name,
              ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS net_sales
            FROM fact_order_line AS f
            JOIN dim_date AS d ON d.date_key = f.date_key
            WHERE f.status = 'completed'
              AND d.year = 2025
            GROUP BY d.month, d.month_name
            ORDER BY d.month
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="top_customers",
        question="Who are the top 5 customers by net sales?",
        explanation=(
            "Top customers by completed net sales across all years. Ties break by name."
        ),
        aliases=(
            "top 5 customers by net sales",
            "show the top 5 customers by net sales",
            "which customers have the highest net sales",
        ),
        sql=_sql(
            """
            SELECT
              c.customer_name,
              c.segment,
              c.region,
              ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS net_sales
            FROM fact_order_line AS f
            JOIN dim_customer AS c ON c.customer_id = f.customer_id
            WHERE f.status = 'completed'
            GROUP BY c.customer_id, c.customer_name, c.segment, c.region
            ORDER BY net_sales DESC, c.customer_name
            LIMIT 5
            """
        ),
    ),
    DemoQuery(
        id="aov_by_channel",
        question="What is the average order value by channel?",
        explanation=(
            "Average order value is completed net sales divided by distinct orders, "
            "split by channel. A multi-line order counts once."
        ),
        aliases=(
            "average order value by channel",
            "show average order value by channel",
            "aov by channel",
        ),
        sql=_sql(
            """
            SELECT
              f.channel,
              ROUND(SUM(f.net_amount_cents) / 100.0 / COUNT(DISTINCT f.order_id), 2)
                AS average_order_value,
              COUNT(DISTINCT f.order_id) AS orders
            FROM fact_order_line AS f
            WHERE f.status = 'completed'
            GROUP BY f.channel
            ORDER BY average_order_value DESC, f.channel
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="returned_products",
        question="Which products have the most returned quantity?",
        explanation=(
            "Products ranked by units on lines with status returned. Completed sales "
            "are not included in this quantity."
        ),
        aliases=(
            "which products were returned most often",
            "most returned products",
            "returned quantity by product",
        ),
        sql=_sql(
            """
            SELECT
              p.product_name,
              p.category,
              SUM(f.quantity) AS returned_quantity
            FROM fact_order_line AS f
            JOIN dim_product AS p ON p.product_id = f.product_id
            WHERE f.status = 'returned'
            GROUP BY p.product_id, p.product_name, p.category
            ORDER BY returned_quantity DESC, p.product_name
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="quarterly_net_sales_2025",
        question="Show quarterly net sales for 2025",
        explanation="Completed net sales by calendar quarter for 2025.",
        aliases=(
            "quarterly net sales for 2025",
            "what were quarterly net sales in 2025",
            "net sales by quarter in 2025",
        ),
        sql=_sql(
            """
            SELECT
              d.quarter,
              ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS net_sales
            FROM fact_order_line AS f
            JOIN dim_date AS d ON d.date_key = f.date_key
            WHERE f.status = 'completed'
              AND d.year = 2025
            GROUP BY d.quarter
            ORDER BY d.quarter
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="signups_2024",
        question="How many customers signed up in 2024?",
        explanation=(
            "Customers whose signup_date falls in calendar 2024. This is a dimension "
            "count and does not require the customer to have placed an order."
        ),
        aliases=(
            "how many new customers signed up in 2024",
            "customer signups in 2024",
            "new customers in 2024",
        ),
        sql=_sql(
            """
            SELECT COUNT(*) AS new_customers
            FROM dim_customer
            WHERE signup_date >= '2024-01-01'
              AND signup_date < '2025-01-01'
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="products_by_category",
        question="How many products are in each category?",
        explanation="Catalog size by category. This counts products, not sales.",
        aliases=(
            "product count by category",
            "how many products per category",
            "list product categories and their counts",
        ),
        sql=_sql(
            """
            SELECT
              category,
              COUNT(*) AS products
            FROM dim_product
            GROUP BY category
            ORDER BY products DESC, category
            LIMIT 100
            """
        ),
    ),
    DemoQuery(
        id="net_sales_by_segment",
        question="What are net sales by customer segment?",
        explanation=(
            "Completed net sales grouped by customer segment (SMB, Mid-Market, Enterprise)."
        ),
        aliases=(
            "net sales by segment",
            "show net sales by customer segment",
            "revenue by customer segment",
        ),
        sql=_sql(
            """
            SELECT
              c.segment,
              ROUND(SUM(f.net_amount_cents) / 100.0, 2) AS net_sales,
              COUNT(DISTINCT f.order_id) AS orders
            FROM fact_order_line AS f
            JOIN dim_customer AS c ON c.customer_id = f.customer_id
            WHERE f.status = 'completed'
            GROUP BY c.segment
            ORDER BY net_sales DESC, c.segment
            LIMIT 100
            """
        ),
    ),
)

SAMPLE_QUESTIONS: tuple[str, ...] = tuple(query.question for query in QUERIES)


def _index(queries: tuple[DemoQuery, ...]) -> dict[str, DemoQuery]:
    index: dict[str, DemoQuery] = {}
    for query in queries:
        for phrase in (query.question, *query.aliases):
            key = normalize_question(phrase)
            existing = index.get(key)
            if existing is not None and existing.id != query.id:
                raise RuntimeError(f"Demo question alias collision: {phrase!r}")
            index[key] = query
    return index


_CATALOG = _index(QUERIES)


def match_question(question: str) -> GeneratedSQL:
    found = _CATALOG.get(normalize_question(question))
    if found is None:
        raise UnrecognizedQuestionError(
            "The offline demo answers a fixed catalog of questions and does not guess SQL. "
            "Ask one of the sample questions, or configure an API key to call a model.",
            list(SAMPLE_QUESTIONS),
        )
    return GeneratedSQL(sql=found.sql, explanation=found.explanation, source="stub")


class StubGenerator:
    """Catalog lookup. `generate` has the same shape as the live model client."""

    def generate(self, question: str) -> GeneratedSQL:
        return match_question(question)
