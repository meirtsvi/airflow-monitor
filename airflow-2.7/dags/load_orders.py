"""Healthy: inserts random orders."""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="load_orders",
    schedule="*/5 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "healthy"],
):
    SQLExecuteQueryOperator(
        task_id="insert_orders",
        conn_id=WAREHOUSE,
        sql="""
            INSERT INTO orders (customer_id, amount)
            SELECT (random() * 100)::int + 1, round((random() * 500)::numeric, 2)
            FROM generate_series(1, 10);
        """,
    )
