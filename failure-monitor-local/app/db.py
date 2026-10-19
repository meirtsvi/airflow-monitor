"""Monitor storage. One row in `failures` per task instance (dag, run, task, map_index);
each new failed try of the same task instance updates that row."""

import psycopg
from psycopg.rows import dict_row

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS failures (
    id            SERIAL PRIMARY KEY,
    dag_id        TEXT NOT NULL,
    run_id        TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    map_index     INT NOT NULL DEFAULT -1,
    try_number    INT NOT NULL,
    failed_at     TIMESTAMPTZ,
    rule_id       TEXT NOT NULL,
    hint          TEXT NOT NULL DEFAULT '',
    matched_text  TEXT NOT NULL DEFAULT '',
    error_excerpt TEXT NOT NULL DEFAULT '',
    log_text      TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL,
    handled_by    TEXT,
    note          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dag_id, run_id, task_id, map_index)
);

CREATE TABLE IF NOT EXISTS actions (
    id         SERIAL PRIMARY KEY,
    failure_id INT NOT NULL REFERENCES failures(id) ON DELETE CASCADE,
    try_number INT NOT NULL,
    action     TEXT NOT NULL,
    actor      TEXT NOT NULL,
    success    BOOLEAN NOT NULL,
    detail     TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect():
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row, autocommit=True)


def init_schema():
    with connect() as conn:
        conn.execute(SCHEMA)


def get_failure_by_key(dag_id, run_id, task_id, map_index):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM failures WHERE dag_id=%s AND run_id=%s AND task_id=%s AND map_index=%s",
            (dag_id, run_id, task_id, map_index),
        ).fetchone()


def upsert_failure(f: dict) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            INSERT INTO failures (dag_id, run_id, task_id, map_index, try_number, failed_at,
                                  rule_id, hint, matched_text, error_excerpt, log_text, status, handled_by)
            VALUES (%(dag_id)s, %(run_id)s, %(task_id)s, %(map_index)s, %(try_number)s, %(failed_at)s,
                    %(rule_id)s, %(hint)s, %(matched_text)s, %(error_excerpt)s, %(log_text)s, %(status)s, NULL)
            ON CONFLICT (dag_id, run_id, task_id, map_index) DO UPDATE SET
                try_number = EXCLUDED.try_number, failed_at = EXCLUDED.failed_at,
                rule_id = EXCLUDED.rule_id, hint = EXCLUDED.hint, matched_text = EXCLUDED.matched_text,
                error_excerpt = EXCLUDED.error_excerpt, log_text = EXCLUDED.log_text,
                status = EXCLUDED.status, handled_by = NULL, note = NULL, updated_at = now()
            RETURNING id
            """,
            f,
        ).fetchone()
        return row["id"]


def set_status(failure_id, status, handled_by=None, note=None):
    with connect() as conn:
        conn.execute(
            """UPDATE failures SET status=%s, handled_by=coalesce(%s, handled_by),
                   note=coalesce(%s, note), updated_at=now() WHERE id=%s""",
            (status, handled_by, note, failure_id),
        )


def add_action(failure_id, try_number, action, actor, success, detail=""):
    with connect() as conn:
        conn.execute(
            "INSERT INTO actions (failure_id, try_number, action, actor, success, detail) VALUES (%s,%s,%s,%s,%s,%s)",
            (failure_id, try_number, action, actor, success, detail),
        )


def auto_attempts(failure_id) -> int:
    with connect() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM actions WHERE failure_id=%s AND actor='auto' AND success",
            (failure_id,),
        ).fetchone()["n"]


# Dashboard filter groups (in addition to filtering by a single exact status).
FILTER_GROUPS = {
    "open": "status IN ('needs_action', 'auto_exhausted')",
    "auto_fixed": "handled_by = 'auto' AND status IN ('recovered', 'resolved')",
    "manual_fixed": "handled_by = 'user' AND status IN ('recovered', 'resolved', 'handled_externally')",
}


def list_failures(status=None, q=""):
    where, params = [], []
    if status in FILTER_GROUPS:
        where.append(FILTER_GROUPS[status])
    elif status:
        where.append("status = %s")
        params.append(status)
    if q:
        where.append("(dag_id ILIKE %s OR task_id ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    query = "SELECT * FROM failures"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY updated_at DESC LIMIT 500"
    with connect() as conn:
        return conn.execute(query, params).fetchall()


def summary():
    with connect() as conn:
        return conn.execute(
            f"""SELECT count(*) FILTER (WHERE {FILTER_GROUPS['open']}) AS open,
                       count(*) FILTER (WHERE status = 'retrying') AS retrying,
                       count(*) FILTER (WHERE {FILTER_GROUPS['auto_fixed']}) AS auto_fixed,
                       count(*) FILTER (WHERE {FILTER_GROUPS['manual_fixed']}) AS manual_fixed,
                       count(*) AS total
                FROM failures"""
        ).fetchone()


def get_failure(failure_id):
    with connect() as conn:
        return conn.execute("SELECT * FROM failures WHERE id=%s", (failure_id,)).fetchone()


def list_actions(failure_id):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM actions WHERE failure_id=%s ORDER BY created_at DESC", (failure_id,)
        ).fetchall()


def rule_hit_counts():
    with connect() as conn:
        rows = conn.execute("SELECT rule_id, count(*) AS n FROM failures GROUP BY rule_id").fetchall()
    return {r["rule_id"]: r["n"] for r in rows}


def failures_in_status(statuses):
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM failures WHERE status = ANY(%s)", (list(statuses),)
        ).fetchall()
