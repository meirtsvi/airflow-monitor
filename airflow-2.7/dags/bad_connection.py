"""Flaky: half the time it reads from a replica host that does not resolve.
Error: could not translate host name "postgres-replica-does-not-exist"
"""

import random

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow import DAG
from airflow.decorators import task
from common import DEFAULT_ARGS, START_DATE

with DAG(
    dag_id="bad_connection",
    schedule="*/5 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "flaky"],
):

    @task
    def read_from_replica():
        conn_id = random.choice(["warehouse", "warehouse_replica"])
        print(f"Using connection {conn_id}")
        rows = PostgresHook(postgres_conn_id=conn_id).get_records("SELECT count(*) FROM orders")
        print(f"orders count: {rows[0][0]}")

    read_from_replica()
