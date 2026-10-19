"""Healthy: rebuilds today's row in sales_daily from orders."""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="daily_sales_agg",
    schedule="*/10 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "healthy"],
):
    SQLExecuteQueryOperator(
        task_id="aggregate_sales",
        conn_id=WAREHOUSE,
        sql="""
            INSERT INTO sales_daily (sales_date, order_count, total_amount)
            SELECT current_date, count(*), coalesce(sum(amount), 0)
            FROM orders
            WHERE created_at::date = current_date
            ON CONFLICT (sales_date) DO UPDATE
            SET order_count = EXCLUDED.order_count,
                total_amount = EXCLUDED.total_amount;
        """,
    )
