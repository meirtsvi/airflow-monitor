#!/usr/bin/env bash
# Stop the local Airflow environment. Pass --wipe to also delete the database volume.
set -euo pipefail
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; else COMPOSE="docker-compose"; fi

if [[ "${1:-}" == "--wipe" ]]; then
  $COMPOSE down -v
else
  $COMPOSE down
fi
