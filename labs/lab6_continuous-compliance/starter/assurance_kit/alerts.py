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
    # TODO 6a: the rule's value for one agent (None = no data, so no alert).
    # points = snapshot[rule.metric] points for this agent whose attributes match rule.where.
    # sum        sum of point values
    # deny_rate  denied / (allowed + denied) using the "outcome" attribute; None if no calls
    # p95        metrics.p95_latency(agent) if metrics is given, else the largest point "max"
    # per_run    sum of values / the agent's agent.runs total; None if no runs
    raise NotImplementedError("Lab 6: _value")


def evaluate(snapshot: dict, rules: list[AlertRule] | None = None, metrics: Any | None = None) -> list[Alert]:
    # TODO 6b: every rule, every agent seen in the snapshot.
    # agents = sorted agent names found in any point's attributes. For each rule and agent: value = _value(...);
    # if value is not None and OPS[rule.op](value, rule.threshold): append Alert(rule.id, rule.title, agent,
    # round(value, 4), rule.threshold, rule.severity, rule.runbook).
    # Return sorted by severity (page, ticket, info), then rule id, then agent.
    raise NotImplementedError("Lab 6: evaluate")
