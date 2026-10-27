-- Demo analytics warehouse (SQLite).
-- Grain of fact_order_line is one row per order line. order_id is not unique.
-- Money is integer cents. Sum cents, then divide by 100.0 for currency units.
-- dim_date is a complete spine from 2022-01-01 through 2025-12-31 so order
-- dates and customer signup dates in that window can both be joined.

PRAGMA foreign_keys = ON;

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

CREATE TABLE dim_customer (
    customer_id INTEGER PRIMARY KEY,
    customer_name TEXT NOT NULL,
    email TEXT NOT NULL,
    segment TEXT NOT NULL CHECK (segment IN ('SMB', 'Mid-Market', 'Enterprise')),
    region TEXT NOT NULL CHECK (region IN ('North', 'South', 'East', 'West', 'EU')),
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    signup_date TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_id INTEGER PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Hardware', 'Software', 'Services')),
    subcategory TEXT NOT NULL,
    list_price_cents INTEGER NOT NULL CHECK (list_price_cents >= 0)
);

CREATE TABLE fact_order_line (
    order_line_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES dim_customer (customer_id),
    product_id INTEGER NOT NULL REFERENCES dim_product (product_id),
    date_key INTEGER NOT NULL REFERENCES dim_date (date_key),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    discount_bps INTEGER NOT NULL CHECK (discount_bps BETWEEN 0 AND 10000),
    gross_amount_cents INTEGER NOT NULL CHECK (gross_amount_cents >= 0),
    net_amount_cents INTEGER NOT NULL CHECK (net_amount_cents >= 0),
    status TEXT NOT NULL CHECK (status IN ('completed', 'cancelled', 'returned', 'pending')),
    channel TEXT NOT NULL CHECK (channel IN ('web', 'partner', 'direct')),
    CHECK (gross_amount_cents = quantity * unit_price_cents)
);

CREATE INDEX idx_fact_order_line_order_id ON fact_order_line (order_id);
CREATE INDEX idx_fact_order_line_customer_id ON fact_order_line (customer_id);
CREATE INDEX idx_fact_order_line_product_id ON fact_order_line (product_id);
CREATE INDEX idx_fact_order_line_date_key ON fact_order_line (date_key);
CREATE INDEX idx_fact_order_line_status ON fact_order_line (status);

-- Row-level exploration view. net_amount is rounded for display.
-- Aggregate net_amount_cents from fact_order_line when the total must tie to cents.
CREATE VIEW v_order_line AS
SELECT
    f.order_line_id,
    f.order_id,
    f.customer_id,
    c.customer_name,
    c.segment,
    c.region,
    c.country,
    c.city,
    f.product_id,
    p.sku,
    p.product_name,
    p.category,
    p.subcategory,
    f.date_key,
    d.full_date AS order_date,
    d.year,
    d.quarter,
    d.month,
    d.month_name,
    f.quantity,
    f.unit_price_cents,
    f.discount_bps,
    f.gross_amount_cents,
    f.net_amount_cents,
    ROUND(f.unit_price_cents / 100.0, 2) AS unit_price,
    ROUND(f.discount_bps / 100.0, 2) AS discount_pct,
    ROUND(f.gross_amount_cents / 100.0, 2) AS gross_amount,
    ROUND(f.net_amount_cents / 100.0, 2) AS net_amount,
    f.status,
    f.channel
FROM fact_order_line AS f
JOIN dim_customer AS c ON c.customer_id = f.customer_id
JOIN dim_product AS p ON p.product_id = f.product_id
JOIN dim_date AS d ON d.date_key = f.date_key;
