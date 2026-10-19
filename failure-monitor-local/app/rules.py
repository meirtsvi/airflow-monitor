"""Load rules.yaml and match a failure against it. First matching rule wins."""

import re
from dataclasses import dataclass

import yaml

from . import config

ACTIONS = {"clear", "mark_success", "none"}
UNCLASSIFIED = "unclassified"


@dataclass
class Rule:
    id: str
    pattern: str
    action: str = "none"
    auto: bool = False
    max_auto_attempts: int = 3
    dag_id: str = ".*"
    task_id: str = ".*"
    hint: str = ""
    description: str = ""


@dataclass
class Match:
    rule: Rule | None
    matched_text: str = ""
    hint: str = ""


def load_rules() -> list[Rule]:
    with open(config.RULES_PATH) as f:
        data = yaml.safe_load(f) or {}
    rules = [Rule(**r) for r in data.get("rules", [])]
    for r in rules:
        if r.action not in ACTIONS:
            raise ValueError(f"rule {r.id}: action must be one of {sorted(ACTIONS)}")
    return rules


def classify(rules: list[Rule], dag_id: str, task_id: str, log_text: str) -> Match:
    for rule in rules:
        if not re.fullmatch(rule.dag_id, dag_id) or not re.fullmatch(rule.task_id, task_id):
            continue
        m = re.search(rule.pattern, log_text, re.IGNORECASE | re.MULTILINE)
        if m:
            groups = {k: v for k, v in m.groupdict().items() if v is not None}
            try:
                hint = rule.hint.format(**groups)
            except (KeyError, IndexError):
                hint = rule.hint
            return Match(rule=rule, matched_text=m.group(0), hint=hint)
    return Match(rule=None)
