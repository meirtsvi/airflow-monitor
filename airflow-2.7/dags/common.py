"""Shared settings for the demo DAGs."""

from datetime import datetime

# retries=0 so failures reach the monitor instead of being retried by Airflow itself.
DEFAULT_ARGS = {"owner": "data-eng", "retries": 0}
START_DATE = datetime(2026, 1, 1)
WAREHOUSE = "warehouse"
