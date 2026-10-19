"""Thin client for the Airflow 2.7 stable REST API (v1), basic auth."""

from datetime import datetime
from urllib.parse import quote

import httpx

from . import config


class AirflowClient:
    def __init__(self):
        # Needs AIRFLOW__API__AUTH_BACKENDS to include airflow.api.auth.backend.basic_auth.
        self._http = httpx.Client(
            base_url=config.AIRFLOW_API_URL,
            timeout=30,
            verify=config.AIRFLOW_VERIFY_SSL,
            auth=(config.AIRFLOW_USERNAME, config.AIRFLOW_PASSWORD),
        )

    def _request(self, method, path, **kwargs):
        resp = self._http.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _ti_path(dag_id, run_id, task_id, map_index):
        path = f"/api/v1/dags/{quote(dag_id, safe='')}/dagRuns/{quote(run_id, safe='')}/taskInstances/{quote(task_id, safe='')}"
        if map_index is not None and map_index >= 0:
            path += f"/{map_index}"
        return path

    def failed_task_instances(self, since: datetime):
        """All failed task instances (any DAG, any run) that ended at or after `since`."""
        items, offset = [], 0
        while True:
            page = self._request(
                "GET",
                "/api/v1/dags/~/dagRuns/~/taskInstances",
                params={
                    "state": "failed",
                    "end_date_gte": since.isoformat(),
                    "limit": 100,
                    "offset": offset,
                },
            )
            items.extend(page["task_instances"])
            offset += len(page["task_instances"])
            if not page["task_instances"] or offset >= page["total_entries"]:
                return items

    def task_instance(self, dag_id, run_id, task_id, map_index):
        return self._request("GET", self._ti_path(dag_id, run_id, task_id, map_index))

    def task_log(self, dag_id, run_id, task_id, map_index, try_number) -> str:
        path = self._ti_path(dag_id, run_id, task_id, None) + f"/logs/{try_number}"
        params = {"full_content": "true"}
        if map_index is not None and map_index >= 0:
            params["map_index"] = map_index
        # text/plain returns the log as-is; the JSON variant wraps it in a stringified list.
        resp = self._http.get(path, params=params, headers={"Accept": "text/plain"})
        resp.raise_for_status()
        return resp.text

    def _clear(self, dag_id, run_id, task_id, map_index, only_failed):
        task = [task_id, map_index] if map_index is not None and map_index >= 0 else task_id
        return self._request(
            "POST",
            f"/api/v1/dags/{quote(dag_id, safe='')}/clearTaskInstances",
            json={
                "dag_run_id": run_id,
                "task_ids": [task],
                "include_downstream": True,
                "only_failed": only_failed,
                "reset_dag_runs": True,
                "dry_run": False,
            },
        )

    def clear(self, dag_id, run_id, task_id, map_index):
        """Retry the task and its downstream tasks in that run."""
        return self._clear(dag_id, run_id, task_id, map_index, only_failed=False)

    def mark_success(self, dag_id, run_id, task_id, map_index):
        """Mark the task success and let the DAG run continue from there."""
        result = self._request(
            "PATCH",
            self._ti_path(dag_id, run_id, task_id, map_index),
            json={"new_state": "success", "dry_run": False},  # dry_run defaults to true in v1
        )
        # Re-run downstream tasks that were failed/upstream_failed. The task itself is now
        # success, so only_failed leaves it alone.
        self._clear(dag_id, run_id, task_id, map_index, only_failed=True)
        # Hand the run back to the scheduler, also when nothing downstream was cleared.
        # It sets the final run state from the task states.
        self._request(
            "PATCH",
            f"/api/v1/dags/{quote(dag_id, safe='')}/dagRuns/{quote(run_id, safe='')}",
            json={"state": "queued"},
        )
        return result
