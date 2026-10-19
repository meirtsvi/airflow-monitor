#!/usr/bin/env bash
# Build and start the failure monitor. Configure the target Airflow in .env.
set -euo pipefail
cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; else COMPOSE="docker-compose"; fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; edit it to point at your Airflow."
fi

# Trust the host's extra CA bundle inside the image (needed behind TLS-inspecting proxies).
HOST_CA="${REQUESTS_CA_BUNDLE:-${SSL_CERT_FILE:-}}"
if [[ -n "$HOST_CA" && -f "$HOST_CA" ]]; then
  cp "$HOST_CA" certs/host-ca.crt
fi

$COMPOSE up -d --build

echo "Waiting for the dashboard..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:8000/rules >/dev/null; then
    echo "Dashboard: http://localhost:8000"
    exit 0
  fi
  sleep 2
done

echo "Dashboard did not start in time. Check: $COMPOSE logs monitor" >&2
exit 1
