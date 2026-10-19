"""Always fails: reads a table that no DAG creates.
Error: relation "staging_events" does not exist"""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="missing_table",
    schedule="*/10 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "broken"],
):
    SQLExecuteQueryOperator(
        task_id="count_events",
        conn_id=WAREHOUSE,
        sql="SELECT count(*) FROM staging_events;",
    )
