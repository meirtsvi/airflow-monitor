-- Runs once, on first start of the postgres container.
-- The "airflow" metadata DB is created by POSTGRES_DB; this adds the warehouse used by the DAGs.

CREATE USER warehouse WITH PASSWORD 'warehouse';
CREATE DATABASE warehouse OWNER warehouse;

-- Restricted role used by the permission_denied DAG.
CREATE USER reporting_ro WITH PASSWORD 'reporting_ro';

\connect warehouse

ALTER SCHEMA public OWNER TO warehouse;
GRANT USAGE ON SCHEMA public TO reporting_ro;

SET ROLE warehouse;

CREATE TABLE salaries (
    employee_id INT PRIMARY KEY,
    amount      NUMERIC(12, 2) NOT NULL
);
INSERT INTO salaries VALUES (1, 10000), (2, 12000);
-- Deliberately no GRANT SELECT ON salaries TO reporting_ro.

CREATE TABLE inventory (
    sku      TEXT PRIMARY KEY,
    quantity INT NOT NULL
);
INSERT INTO inventory VALUES ('SKU-1', 10);

CREATE TABLE customers (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    customer_id INT NOT NULL,
    amount      NUMERIC(12, 2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sales_daily (
    sales_date   DATE PRIMARY KEY,
    order_count  INT NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL
);

CREATE TABLE audit_log (
    id      INT PRIMARY KEY,
    message TEXT NOT NULL
);
