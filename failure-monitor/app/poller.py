"""Background loop: detect failed tasks -> fetch log -> classify -> act."""

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from . import config, db
from .airflow_client import AirflowClient
from .rules import UNCLASSIFIED, classify, load_rules

log = logging.getLogger("poller")

OVERLAP = timedelta(minutes=5)
EXCERPT_CONTEXT_LINES = 3
EXCERPT_MAX_LINES = 40


def run_action(client: AirflowClient, failure: dict, action: str):
    args = (failure["dag_id"], failure["run_id"], failure["task_id"], failure["map_index"])
    if action == "clear":
        return client.clear(*args)
    if action == "mark_success":
        return client.mark_success(*args)
    raise ValueError(f"unknown action {action}")


def make_excerpt(log_text: str, matched_text: str) -> str:
    lines = log_text.splitlines()
    idx = None
    if matched_text:
        idx = next((i for i, line in enumerate(lines) if matched_text in line), None)
    if idx is None:
        idx = next((i for i, line in enumerate(lines) if "[ERROR]" in line or " ERROR - " in line or "Traceback" in line), None)
    if idx is None:
        return "\n".join(lines[-EXCERPT_MAX_LINES:])
    start = max(0, idx - EXCERPT_CONTEXT_LINES)
    return "\n".join(lines[start : start + EXCERPT_MAX_LINES])


class Poller:
    def __init__(self, client: AirflowClient):
        self.client = client
        self.since = datetime.now(timezone.utc) - timedelta(hours=config.INITIAL_LOOKBACK_HOURS)
        self.last_poll_at = None
        self.last_error = None

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="poller").start()

    def _loop(self):
        while True:
            started = datetime.now(timezone.utc)
            try:
                self.poll_once()
                self.since = started - OVERLAP
                self.last_error = None
            except Exception as e:  # keep polling even if Airflow is down
                self.last_error = f"{type(e).__name__}: {e}"
                log.exception("poll failed")
            self.last_poll_at = started
            time.sleep(config.POLL_INTERVAL_SECONDS)

    def poll_once(self):
        rules = load_rules()  # re-read every poll so rules.yaml edits apply without restart
        for ti in self.client.failed_task_instances(self.since):
            self._handle_failed_ti(ti, rules)
        self._check_retries()

    def _handle_failed_ti(self, ti: dict, rules):
        key = (ti["dag_id"], ti["dag_run_id"], ti["task_id"], ti.get("map_index", -1))
        existing = db.get_failure_by_key(*key)
        if existing and existing["try_number"] >= ti["try_number"]:
            return  # this try was already processed

        log_text = self.client.task_log(*key, ti["try_number"])
        match = classify(rules, ti["dag_id"], ti["task_id"], log_text)
        rule = match.rule

        failure = {
            "dag_id": key[0],
            "run_id": key[1],
            "task_id": key[2],
            "map_index": key[3],
            "try_number": ti["try_number"],
            "failed_at": ti.get("end_date"),
            "rule_id": rule.id if rule else UNCLASSIFIED,
            "hint": match.hint,
            "matched_text": match.matched_text,
            "error_excerpt": make_excerpt(log_text, match.matched_text),
            "log_text": log_text,
            "status": "needs_action",
        }
        failure_id = db.upsert_failure(failure)
        log.info("failure %s.%s run=%s try=%s rule=%s", key[0], key[2], key[1], ti["try_number"], failure["rule_id"])

        if not rule or not rule.auto or rule.action == "none":
            return
        if db.auto_attempts(failure_id) >= rule.max_auto_attempts:
            db.set_status(failure_id, "auto_exhausted")
            return

        failure["id"] = failure_id
        try:
            run_action(self.client, failure, rule.action)
            db.add_action(failure_id, ti["try_number"], rule.action, "auto", True, f"rule {rule.id}")
            db.set_status(failure_id, "retrying" if rule.action == "clear" else "resolved", handled_by="auto")
        except Exception as e:
            db.add_action(failure_id, ti["try_number"], rule.action, "auto", False, str(e))
            log.exception("auto action failed")

    def _check_retries(self):
        """A cleared task that now succeeded is marked recovered. A new failed try is
        picked up by the failed-task query instead."""
        for f in db.failures_in_status(["retrying"]):
            ti = self.client.task_instance(f["dag_id"], f["run_id"], f["task_id"], f["map_index"])
            if ti.get("state") == "success":
                db.set_status(f["id"], "recovered")
