#!/usr/bin/env bash
# Start the local Airflow 2.7 environment and wait until the webserver is healthy.
set -euo pipefail
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; else COMPOSE="docker-compose"; fi

$COMPOSE up -d --build

echo "Waiting for Airflow webserver..."
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8081/health >/dev/null; then
    echo "Airflow 2.7 is up."
    echo "  UI:       http://localhost:8081  (user/password from .env)"
    echo "  Postgres: localhost:5434  (warehouse/warehouse, db warehouse)"
    exit 0
  fi
  sleep 5
done

echo "Airflow did not become healthy in time. Check: $COMPOSE logs airflow-webserver" >&2
exit 1
