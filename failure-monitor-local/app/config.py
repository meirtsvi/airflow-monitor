import os

AIRFLOW_API_URL = os.environ.get("AIRFLOW_API_URL", "http://localhost:8080").rstrip("/")
AIRFLOW_UI_URL = os.environ.get("AIRFLOW_UI_URL", AIRFLOW_API_URL).rstrip("/")
AIRFLOW_USERNAME = os.environ["AIRFLOW_USERNAME"]
AIRFLOW_PASSWORD = os.environ["AIRFLOW_PASSWORD"]
AIRFLOW_VERIFY_SSL = os.environ.get("AIRFLOW_VERIFY_SSL", "true").lower() == "true"

DATABASE_URL = os.environ["DATABASE_URL"]
RULES_PATH = os.environ.get("RULES_PATH", "rules.yaml")
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
# How far back to look for failures when the monitor starts.
INITIAL_LOOKBACK_HOURS = int(os.environ.get("INITIAL_LOOKBACK_HOURS", "24"))
