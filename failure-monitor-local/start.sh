#!/usr/bin/env bash
# Run the failure monitor without Docker: a private Postgres 16 cluster in .pgdata/ and the
# app in a Python virtualenv in .venv/. Needs Homebrew's postgresql@16 and python3.12.
set -euo pipefail
cd "$(dirname "$0")"

PG_BIN="${PG_BIN:-$(brew --prefix postgresql@16)/bin}"
PYTHON="${PYTHON:-python3.12}"
PG_PORT=5433
APP_PORT=8000

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example; edit it to point at your Airflow."
fi

pg_running() { [[ -d .pgdata ]] && "$PG_BIN/pg_ctl" -D .pgdata status >/dev/null 2>&1; }
app_running() { [[ -f monitor.pid ]] && kill -0 "$(cat monitor.pid)" 2>/dev/null; }
port_busy() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# Same ports as the Docker version, so only one of them can run at a time.
if { ! pg_running && port_busy $PG_PORT; } || { ! app_running && port_busy $APP_PORT; }; then
  echo "Port $PG_PORT or $APP_PORT is in use. Stop the Docker monitor first (failure-monitor/stop.sh)." >&2
  exit 1
fi

# Postgres
if [[ ! -d .pgdata ]]; then
  "$PG_BIN/initdb" -D .pgdata -U monitor --encoding=UTF8 --locale=en_US.UTF-8 --auth=scram-sha-256 --pwfile=<(echo monitor) >/dev/null
  NEW_CLUSTER=1
fi
if ! pg_running; then
  "$PG_BIN/pg_ctl" -D .pgdata -l postgres.log -w \
    -o "-p $PG_PORT -c listen_addresses=localhost -k '$PWD/.pgdata'" start >/dev/null
fi
if [[ -n "${NEW_CLUSTER:-}" ]]; then
  PGPASSWORD=monitor "$PG_BIN/createdb" -h localhost -p $PG_PORT -U monitor monitor
fi

# App
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/pip install -q --disable-pip-version-check -r requirements.txt

if app_running; then
  echo "Monitor already running (pid $(cat monitor.pid))."
else
  set -a; source .env; set +a
  nohup .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $APP_PORT >monitor.log 2>&1 &
  echo $! >monitor.pid
fi

echo "Waiting for the dashboard..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:$APP_PORT/rules >/dev/null; then
    echo "Dashboard: http://localhost:$APP_PORT  (logs: monitor.log, postgres.log)"
    exit 0
  fi
  sleep 1
done

echo "Dashboard did not start in time. Check monitor.log" >&2
exit 1
