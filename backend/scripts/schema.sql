-- ============================================================
-- InsightForge sample e-commerce schema
-- A small but realistic star-ish model: customers place orders,
-- orders contain line items of products, and payments settle orders.
-- ============================================================

DROP TABLE IF EXISTS payments     CASCADE;
DROP TABLE IF EXISTS order_items   CASCADE;
DROP TABLE IF EXISTS orders        CASCADE;
DROP TABLE IF EXISTS products      CASCADE;
DROP TABLE IF EXISTS customers     CASCADE;

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    email       TEXT        NOT NULL UNIQUE,
    city        TEXT        NOT NULL,
    country     TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        TEXT          NOT NULL,
    category    TEXT          NOT NULL,
    price       NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    cost        NUMERIC(10,2) NOT NULL CHECK (cost  >= 0),
    stock       INT           NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id           SERIAL PRIMARY KEY,
    customer_id  INT         NOT NULL REFERENCES customers(id),
    order_date   DATE        NOT NULL,
    status       TEXT        NOT NULL DEFAULT 'completed',  -- completed|pending|cancelled|refunded
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INT           NOT NULL REFERENCES orders(id),
    product_id  INT           NOT NULL REFERENCES products(id),
    quantity    INT           NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE payments (
    id        SERIAL PRIMARY KEY,
    order_id  INT           NOT NULL REFERENCES orders(id),
    amount    NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    method    TEXT          NOT NULL,  -- card|paypal|bank_transfer|cash
    status    TEXT          NOT NULL DEFAULT 'paid',  -- paid|failed|refunded
    paid_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Indexes that matter for the analytical queries the LLM will write.
CREATE INDEX idx_orders_customer   ON orders(customer_id);
CREATE INDEX idx_orders_date       ON orders(order_date);
CREATE INDEX idx_items_order       ON order_items(order_id);
CREATE INDEX idx_items_product     ON order_items(product_id);
CREATE INDEX idx_payments_order    ON payments(order_id);
