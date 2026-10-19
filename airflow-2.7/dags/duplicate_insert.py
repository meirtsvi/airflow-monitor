"""Fails after the first run: inserts a fixed primary key.
Error: duplicate key value violates unique constraint "audit_log_pkey" """

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="duplicate_insert",
    schedule="*/10 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "broken"],
):
    write_audit_row = SQLExecuteQueryOperator(
        task_id="write_audit_row",
        conn_id=WAREHOUSE,
        sql="INSERT INTO audit_log (id, message) VALUES (1, 'nightly run');",
    )

    count_audit_rows = SQLExecuteQueryOperator(
        task_id="count_audit_rows",
        conn_id=WAREHOUSE,
        sql="SELECT count(*) FROM audit_log;",
    )

    write_audit_row >> count_audit_rows
