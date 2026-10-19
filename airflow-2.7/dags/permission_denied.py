"""Always fails: the read-only role has no SELECT grant on salaries.
Error: permission denied for table salaries"""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE

with DAG(
    dag_id="permission_denied",
    schedule="*/10 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "broken"],
):
    SQLExecuteQueryOperator(
        task_id="export_salaries",
        conn_id="warehouse_readonly",
        sql="SELECT sum(amount) FROM salaries;",
    )
