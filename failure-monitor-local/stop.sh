#!/usr/bin/env bash
# Stop the local failure monitor and its Postgres. Pass --wipe to also delete the database (.pgdata/).
set -euo pipefail
cd "$(dirname "$0")"

PG_BIN="${PG_BIN:-$(brew --prefix postgresql@16)/bin}"

if [[ -f monitor.pid ]]; then
  kill "$(cat monitor.pid)" 2>/dev/null || true
  rm -f monitor.pid
fi

if [[ -d .pgdata ]] && "$PG_BIN/pg_ctl" -D .pgdata status >/dev/null 2>&1; then
  "$PG_BIN/pg_ctl" -D .pgdata -m fast stop >/dev/null
fi

if [[ "${1:-}" == "--wipe" ]]; then
  rm -rf .pgdata
fi
echo "Stopped."
