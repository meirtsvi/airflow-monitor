"""Flaky: a 1s statement_timeout against a query that sleeps 0-2s. Fails about half the time.
Error: canceling statement due to statement timeout"""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="flaky_statement_timeout",
    schedule="*/5 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "flaky"],
):
    SQLExecuteQueryOperator(
        task_id="slow_report_query",
        conn_id=WAREHOUSE,
        sql="SET statement_timeout = 1000; SELECT pg_sleep(random() * 2);",
    )
