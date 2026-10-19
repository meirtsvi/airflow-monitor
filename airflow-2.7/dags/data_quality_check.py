"""Fails whenever load_customers has inserted a customer with no email.
Error: SQLCheckOperator "Test failed." """

from airflow.providers.common.sql.operators.sql import SQLCheckOperator
from airflow import DAG
from common import DEFAULT_ARGS, START_DATE, WAREHOUSE

with DAG(
    dag_id="data_quality_check",
    schedule="*/10 * * * *",
    start_date=START_DATE,
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["demo", "quality"],
):
    SQLCheckOperator(
        task_id="customers_have_email",
        conn_id=WAREHOUSE,
        sql="SELECT count(*) = 0 FROM customers WHERE email IS NULL;",
    )
