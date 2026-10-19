"""Flaky: one task holds a row lock for 30s while a parallel task tries to update the same row
with a 3s lock_timeout. Retrying the update after the holder finishes succeeds.
Error: canceling statement due to lock timeout"""

from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="flaky_lock_timeout",
    schedule="*/10 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "flaky"],
):
    # Both statements run in one transaction, so the lock is held until the sleep ends.
    SQLExecuteQueryOperator(
        task_id="hold_inventory_lock",
        conn_id=WAREHOUSE,
        sql="SELECT sku FROM inventory WHERE sku = 'SKU-1' FOR UPDATE; SELECT pg_sleep(30);",
    )

    SQLExecuteQueryOperator(
        task_id="update_inventory",
        conn_id=WAREHOUSE,
        sql="""
            SELECT pg_sleep(5);
            SET lock_timeout = '3s';
            UPDATE inventory SET quantity = quantity + 1 WHERE sku = 'SKU-1';
        """,
    )
