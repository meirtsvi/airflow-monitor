# Airflow failure monitor

Airflow environment and failure monitor:

| Folder | What | Start | URL |
|---|---|---|---|
| `airflow-2.7/` | Airflow 2.7.3 (LocalExecutor) + Postgres with 10 demo SQL DAGs | `airflow-2.7/start.sh` | http://localhost:8081 (airflow / airflow), Postgres on 5434 |
| `failure-monitor-local/` | The monitor source (`app/`, `rules.yaml`), run without Docker: Postgres 16 cluster in `.pgdata/` + Python venv in `.venv/`. Polls the Airflow 2.7 REST API (`airflow-2.7` by default), classifies failures with rules, auto-repairs, dashboard | `failure-monitor-local/start.sh` | http://localhost:8000, Postgres on 5433 |
| `failure-monitor/` | The same monitor in Docker; the image copies the source from `failure-monitor-local/` | `failure-monitor/start.sh` | http://localhost:8000, Postgres on 5433 |

Stop with `stop.sh` in each folder (`stop.sh --wipe` also deletes the database).
DAGs, rules and code are copied into the images, so re-run `start.sh` after editing them.

The two monitor versions use the same ports, so run one at a time. Each has its own database and `.env`.
The local version needs Homebrew's `postgresql@16` and `python3.12`; it writes `monitor.log` and `postgres.log` in its folder.
Restart it (`stop.sh` + `start.sh`) after editing code; `rules.yaml` is re-read on every poll.

New DAGs start paused. Unpause them in the Airflow UI (or via `PATCH /api/v1/dags/{dag_id}` with `{"is_paused": false}`).

## Pointing the monitor at another Airflow
Edit `.env` in the monitor folder you run (`failure-monitor-local/.env` or `failure-monitor/.env`):
- `AIRFLOW_API_URL`: API base URL as seen by the monitor (from inside the container for the Docker version)
- `AIRFLOW_UI_URL`: base URL for "open in Airflow" links, as seen from your browser
- `AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD`: a user allowed to read task instances and logs, and to clear / set task state

The monitor needs an Airflow 2.x stable API (`/api/v1`, tested on 2.7.3) with basic auth enabled:
`AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session`.
It does not work with Airflow 3 (`/api/v2`) anymore.

## How it works
Every `POLL_INTERVAL_SECONDS` the monitor:
1. `GET /api/v1/dags/~/dagRuns/~/taskInstances?state=failed&end_date_gte=...` (all DAGs, offset pagination)
2. For each new failed try: `GET .../taskInstances/{task}/logs/{try}` (as `text/plain`), then matches the log against `failure-monitor-local/rules.yaml` (first match wins)
3. If the rule is `auto: true` and under `max_auto_attempts`: runs the action
   (`clear` = `POST /api/v1/dags/{dag}/clearTaskInstances` with downstream, `mark_success` = `PATCH .../taskInstances/{task}` to success with `dry_run: false`, then clear its failed/upstream_failed downstream tasks and set the run to `queued` so the run continues)
4. Checks tasks it retried; if they now succeed the failure becomes `recovered`

One row per task instance (dag, run, task, map index); a new failed try of the same task updates that row.

Statuses: `needs_action`, `auto_exhausted` (auto retries used up) are open; `retrying` waits for the re-run;
`recovered`, `resolved` (marked success), `handled_externally` (user note) are closed.

## Demo DAGs
| DAG | Behaviour | Rule |
|---|---|---|
| load_customers, load_orders, daily_sales_agg | healthy | - |
| flaky_statement_timeout | fails ~50% on statement_timeout | pg_statement_timeout (auto clear) |
| flaky_lock_timeout | lock held by a parallel task | pg_lock_timeout (auto clear) |
| bad_connection | 50% uses an unresolvable host | db_host_unreachable (auto clear) |
| missing_table | table doesn't exist | missing_relation (manual) |
| duplicate_insert | fixed primary key, fails after first run; has a downstream task | duplicate_key (manual, suggests mark success) |
| permission_denied | role lacks SELECT grant | permission_denied (manual) |
| data_quality_check | fails when a customer has no email | data_quality_failed (manual) |
