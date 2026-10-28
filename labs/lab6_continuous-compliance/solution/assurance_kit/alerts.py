"""Evaluate alert rules against a metrics snapshot, per agent (rubric 7.3)."""
from __future__ import annotations

import operator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

ALERTS_PATH = Path(__file__).parent / "policies" / "alerts.yaml"
OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "==": operator.eq}


class AlertRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    title: str
    metric: str
    where: dict[str, str] = Field(default_factory=dict)
    agg: Literal["sum", "deny_rate", "p95", "per_run"]
    op: Literal[">", ">=", "<", "=="]
    threshold: float
    severity: Literal["page", "ticket", "info"]
    runbook: str


@dataclass
class Alert:
    rule: str
    title: str
    agent: str
    value: float
    threshold: float
    severity: str
    runbook: str

    def line(self) -> str:
        return f"{self.severity.upper():6} {self.rule:20} {self.agent:17} {self.value:g} (threshold {self.threshold:g})"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_rules(path: str | Path = ALERTS_PATH) -> list[AlertRule]:
    return [AlertRule.model_validate(r) for r in yaml.safe_load(Path(path).read_text(encoding="utf-8"))["rules"]]


def _value(rule: AlertRule, snapshot: dict, agent: str, metrics: Any | None) -> float | None:
    points = [p for p in snapshot.get(rule.metric, []) if p["attributes"].get("agent") == agent
              and all(p["attributes"].get(k) == v for k, v in rule.where.items())]
    if rule.agg == "sum":
        return sum(p["value"] for p in points)
    if rule.agg == "deny_rate":
        allowed = sum(p["value"] for p in points if p["attributes"].get("outcome") == "allowed")
        denied = sum(p["value"] for p in points if p["attributes"].get("outcome") == "denied")
        return denied / (allowed + denied) if allowed + denied else None
    if rule.agg == "p95":
        return metrics.p95_latency(agent) if metrics is not None else max((p["max"] for p in points), default=None)
    if rule.agg == "per_run":
        runs = sum(p["value"] for p in snapshot.get("agent.runs", []) if p["attributes"].get("agent") == agent)
        return sum(p["value"] for p in points) / runs if runs else None
    return None


def evaluate(snapshot: dict, rules: list[AlertRule] | None = None, metrics: Any | None = None) -> list[Alert]:
    rules = rules or load_rules()
    agents = sorted({p["attributes"]["agent"] for pts in snapshot.values() for p in pts if "agent" in p["attributes"]})
    fired = []
    for rule in rules:
        for agent in agents:
            value = _value(rule, snapshot, agent, metrics)
            if value is not None and OPS[rule.op](value, rule.threshold):
                fired.append(Alert(rule.id, rule.title, agent, round(value, 4), rule.threshold, rule.severity,
                                   rule.runbook))
    order = {"page": 0, "ticket": 1, "info": 2}
    return sorted(fired, key=lambda a: (order[a.severity], a.rule, a.agent))
