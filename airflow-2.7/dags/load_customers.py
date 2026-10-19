"""Healthy: loads a few customers. About 1 in 3 runs inserts a customer with no email,
which makes data_quality_check fail."""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="load_customers",
    schedule="*/5 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "healthy"],
):
    SQLExecuteQueryOperator(
        task_id="insert_customers",
        conn_id=WAREHOUSE,
        sql="""
            INSERT INTO customers (name, email)
            SELECT 'customer_' || g,
                   CASE WHEN random() < 0.33 AND g = 1 THEN NULL ELSE 'customer_' || g || '@example.com' END
            FROM generate_series(1, 3) g;
        """,
    )
