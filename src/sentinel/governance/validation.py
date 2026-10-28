"""Validation records (M11-L03, L04): fit for THIS intended use, in THIS configuration, judged independently.

A record pins the fleet fingerprint it validated. Any change to the model, prompt, tools, permission mode,
controls or configs changes the fingerprint, and the record goes stale until someone re-validates: the same
rule as change control (rubric 7.4), seen from the validator's side.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .inventory import PERSON, POLICIES, person

VALIDATIONS_PATH = POLICIES / "validations.yaml"
Method = Literal["scripted", "unscripted", "exploratory", "ongoing_monitoring", "outcomes_analysis",
                 "conceptual_soundness", "effective_challenge", "red_team"]
# The classic model-risk validation elements a bank's AI policy applies to an agent SR 26-2 doesn't cover.
MRM_ELEMENTS = ("conceptual_soundness", "outcomes_analysis", "ongoing_monitoring", "effective_challenge")


class Activity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    method: Method
    what: str = Field(min_length=10)
    evidence: str                      # "rubric:7.1" (status read from the scorecard) or a named record
    result: str

    @property
    def rubric(self) -> str | None:
        return self.evidence.split(":", 1)[1] if self.evidence.startswith("rubric:") else None


class ValidationRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^VAL-[A-Z]+-\d{3}$")
    agent: str
    framework: Literal["CSA", "MRM", "RISK-BASED"]
    intended_use: str = Field(min_length=20)
    process_risk: Literal["high", "not_high"]
    developer: str = Field(pattern=PERSON)
    validator: str = Field(pattern=PERSON)
    validated_fingerprint: str = Field(pattern=r"^fp:[0-9a-f]{16}$")
    date: date
    activities: list[Activity] = Field(min_length=1)
    conclusion: Literal["fit", "fit_with_conditions", "not_fit"]
    conditions: list[str] = Field(default_factory=list)
    revalidate_on: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _conditions(self) -> ValidationRecord:
        if self.conclusion == "fit_with_conditions" and not self.conditions:
            raise ValueError(f"{self.id}: 'fit_with_conditions' must list the conditions")
        return self

    @property
    def methods(self) -> set[str]:
        return {a.method for a in self.activities}


class ValidationSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    as_of: date
    records: list[ValidationRecord]

    def latest(self, agent: str) -> ValidationRecord | None:
        mine = [r for r in self.records if r.agent == agent]
        return max(mine, key=lambda r: r.date) if mine else None


def load_validations(path: str | Path = VALIDATIONS_PATH) -> ValidationSet:
    return ValidationSet.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def status(record: ValidationRecord | None, fleet) -> str:
    """'current', 'stale' (the agent changed since validation) or 'missing'."""
    if record is None:
        return "missing"
    return "current" if fleet.get(record.agent).fingerprint() == record.validated_fingerprint else "stale"


def lint_validations(vs: ValidationSet, fleet, rubric_ids: set[str], confirmed=None) -> list[str]:
    points = {i.id: (i.points, i.status) for i in confirmed.items} if confirmed is not None else {}
    names = {a.name for a in fleet.agents}
    problems: list[str] = []
    for name in sorted(names - {r.agent for r in vs.records}):
        problems.append(f"VAL-006 {name}: in production with no validation record")
    for r in vs.records:
        if r.agent not in names:
            problems.append(f"VAL-008 {r.id}: agent {r.agent!r} isn't in the fleet")
            continue
        if person(r.validator) == person(r.developer):
            problems.append(f"VAL-001 {r.id}: validated by its developer; validation must be independent")
        if r.framework == "CSA" and r.process_risk == "high" and "scripted" not in r.methods:
            problems.append(f"VAL-002 {r.id}: high process risk under CSA with no scripted testing (course rule)")
        if r.framework == "MRM" and (gap := [e for e in MRM_ELEMENTS if e not in r.methods]):
            problems.append(f"VAL-003 {r.id}: MRM validation missing {', '.join(gap)}")
        if r is vs.latest(r.agent) and status(r, fleet) == "stale":
            problems.append(f"VAL-004 {r.id}: validated {r.validated_fingerprint}, but {r.agent} now runs "
                            f"{fleet.get(r.agent).fingerprint()}: re-validate before relying on this record")
        for a in r.activities:
            if a.rubric and a.rubric not in rubric_ids:
                problems.append(f"VAL-007 {r.id}: activity cites unknown rubric item {a.rubric}")
            elif a.rubric and points and not points[a.rubric][0] and r.conclusion == "fit":
                problems.append(f"VAL-005 {r.id}: concluded 'fit' on evidence {a.rubric}, which is "
                                f"{points[a.rubric][1]} after review; conclude 'fit_with_conditions' or fix it")
    return problems


def summary_md(vs: ValidationSet, fleet) -> str:
    lines = ["| Agent | Record | Framework | Process risk | Validator | Conclusion | Configuration |",
             "|---|---|---|---|---|---|---|"]
    for a in fleet.agents:
        r = vs.latest(a.name)
        if r is None:
            lines.append(f"| {a.name} | (none) | | | | | **missing** |")
            continue
        concl = r.conclusion.replace("_", " ") + (f": {'; '.join(r.conditions)}" if r.conditions else "")
        lines.append(f"| {a.name} | {r.id} ({r.date}) | {r.framework} | {r.process_risk.replace('_', ' ')} | "
                     f"{r.validator} | {concl} | **{status(r, fleet)}** |")
    return "\n".join(lines)
