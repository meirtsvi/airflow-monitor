import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import config, db
from .airflow_client import AirflowClient
from .poller import Poller, run_action
from .rules import UNCLASSIFIED, load_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

client = AirflowClient()
poller = Poller(client)


@asynccontextmanager
async def lifespan(app):
    db.init_schema()
    poller.start()
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# status -> (label, icon, tone). Tone picks the badge color; icon + label carry the meaning.
STATUS_STYLE = {
    "needs_action": ("Needs action", "!", "critical"),
    "auto_exhausted": ("Retries exhausted", "!", "critical"),
    "retrying": ("Retrying", "↻", "warning"),
    "recovered": ("Recovered", "✓", "good"),
    "resolved": ("Marked success", "✓", "good"),
    "handled_externally": ("Handled externally", "✓", "info"),
}

# Summary cards, which double as the main filters.
SUMMARY_CARDS = [
    ("open", "Open", "Need a human"),
    ("retrying", "Retrying", "Waiting for re-run"),
    ("auto_fixed", "Fixed automatically", "By a rule"),
    ("manual_fixed", "Handled manually", "By a person"),
]


def airflow_task_url(f):
    url = f"{config.AIRFLOW_UI_URL}/dags/{quote(f['dag_id'], safe='')}/grid?dag_run_id={quote(f['run_id'], safe='')}&task_id={quote(f['task_id'], safe='')}"
    if f["map_index"] >= 0:
        url += f"&map_index={f['map_index']}"
    return url


def timeago(dt):
    if dt is None:
        return ""
    seconds = int((datetime.now(timezone.utc) - dt).total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds // size}{unit} ago"
    return "just now"


templates.env.globals["airflow_task_url"] = airflow_task_url
templates.env.globals["STATUS_STYLE"] = STATUS_STYLE
templates.env.filters["timeago"] = timeago


def rules_by_id():
    try:
        return {r.id: r for r in load_rules()}, None
    except Exception as e:
        return {}, f"Cannot load rules: {e}"


@app.get("/", response_class=HTMLResponse)
def failures_page(request: Request, status: str = "open", q: str = ""):
    return templates.TemplateResponse(request, "failures.html", {"status": status, "q": q, "page": "failures"})


@app.get("/partials/failures", response_class=HTMLResponse)
def failures_partial(request: Request, status: str = "open", q: str = ""):
    rules, rules_error = rules_by_id()
    return templates.TemplateResponse(
        request,
        "_failures_table.html",
        {
            "failures": db.list_failures(None if status == "all" else status, q.strip()),
            "status": status,
            "q": q,
            "rules": rules,
            "rules_error": rules_error,
            "summary": db.summary(),
            "cards": SUMMARY_CARDS,
            "poller": poller,
        },
    )


@app.get("/failures/{failure_id}", response_class=HTMLResponse)
def failure_detail(request: Request, failure_id: int):
    f = db.get_failure(failure_id)
    if not f:
        raise HTTPException(404)
    rules, _ = rules_by_id()
    return templates.TemplateResponse(
        request,
        "failure_detail.html",
        {"f": f, "rule": rules.get(f["rule_id"]), "actions": db.list_actions(failure_id), "page": "failures"},
    )


@app.post("/failures/{failure_id}/action")
def failure_action(failure_id: int, action: str = Form(...), note: str = Form(""), back: str = Form("/")):
    f = db.get_failure(failure_id)
    if not f:
        raise HTTPException(404)

    if action == "handled_externally":
        if not note.strip():
            raise HTTPException(400, "A note is required")
        db.add_action(failure_id, f["try_number"], action, "user", True, note)
        db.set_status(failure_id, "handled_externally", handled_by="user", note=note)
    elif action in ("clear", "mark_success"):
        try:
            run_action(client, f, action)
        except Exception as e:
            db.add_action(failure_id, f["try_number"], action, "user", False, str(e))
            raise HTTPException(502, f"Airflow call failed: {e}")
        db.add_action(failure_id, f["try_number"], action, "user", True, note)
        db.set_status(failure_id, "retrying" if action == "clear" else "resolved", handled_by="user", note=note or None)
    else:
        raise HTTPException(400, f"Unknown action {action}")

    return RedirectResponse(back, status_code=303)


@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request):
    rules, rules_error = rules_by_id()
    return templates.TemplateResponse(
        request,
        "rules.html",
        {
            "rules": list(rules.values()),
            "rules_error": rules_error,
            "hits": db.rule_hit_counts(),
            "unclassified": UNCLASSIFIED,
            "rules_path": config.RULES_PATH,
            "page": "rules",
        },
    )
