"""Agent risk register as an FMEA (M11-L02): failure modes, controls tied to rubric items, severity-first priority.

Each row's controls name the rubric item that proves them. When a review withholds that item's point (failing,
challenged, unconfirmed), the register flags every rating that assumed the control: a risk score is only as
good as the controls it counts.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .inventory import PERSON, POLICIES, person

REGISTER_PATH = POLICIES / "risk_register.yaml"
Priority = Literal["High", "Medium", "Low"]
BOARD = ("board", "risk committee")


def priority(s: int, o: int, d: int) -> Priority:
    """Course priority rule, severity first (the idea behind AIAG-VDA Action Priority, not its table).

    High:   severity 9-10 and (occurrence >= 4 or detection >= 7), or severity >= 7 and occurrence >= 6
    Medium: severity 9-10 otherwise (unless occurrence is 1), severity >= 7 with occurrence >= 3 or detection
            >= 5, or any severity >= 4 that happens monthly or more
    Low:    everything else
    """
    if (s >= 9 and (o >= 4 or d >= 7)) or (s >= 7 and o >= 6):
        return "High"
    if (s >= 9 and o >= 2) or (s >= 7 and (o >= 3 or d >= 5)) or (s >= 4 and o >= 6):
        return "Medium"
    return "Low"


class Control(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    rubric: str = Field(pattern=r"^[1-7]\.[1-6]$")
    how: str = Field(min_length=10)


class Action(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    what: str = Field(min_length=10)
    owner: str = Field(pattern=PERSON)
    due: date


class Acceptance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    by: str = Field(min_length=5)                 # a person ("S. Patel, Chief Compliance Officer") or a committee
    date: date
    expires: date
    rationale: str = Field(min_length=10)


class FailureMode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^FM-[A-Z]+-\d{2}$")
    agent: str
    step: str
    failure_mode: str = Field(min_length=10)
    effect: str = Field(min_length=10)
    cause: str = Field(min_length=5)
    controls: list[Control] = Field(default_factory=list)
    s: int = Field(ge=1, le=10)
    o: int = Field(ge=1, le=10)
    d: int = Field(ge=1, le=10)
    owner: str = Field(pattern=PERSON)
    action: Action | None = None
    acceptance: Acceptance | None = None

    @property
    def rpn(self) -> int:
        return self.s * self.o * self.d

    @property
    def priority(self) -> Priority:
        return priority(self.s, self.o, self.d)

    @property
    def treatment(self) -> str:
        if self.action:
            return f"action due {self.action.due}, owner {person(self.action.owner)}"
        if self.acceptance:
            return f"accepted by {person(self.acceptance.by)} until {self.acceptance.expires}"
        return "monitor" if self.priority == "Low" else "NONE"


class RiskRegister(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    as_of: date
    scales: dict[str, dict[int, str]]
    failure_modes: list[FailureMode]

    @model_validator(mode="after")
    def _unique(self) -> RiskRegister:
        ids = [f.id for f in self.failure_modes]
        if len(ids) != len(set(ids)):
            raise ValueError("failure mode ids must be unique")
        return self

    def for_agent(self, agent: str | None = None) -> list[FailureMode]:
        rows = [f for f in self.failure_modes if agent in (None, f.agent)]
        order = {"High": 0, "Medium": 1, "Low": 2}
        return sorted(rows, key=lambda f: (order[f.priority], -f.s, -f.rpn))


def load_register(path: str | Path = REGISTER_PATH) -> RiskRegister:
    return RiskRegister.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def lint_register(reg: RiskRegister, fleet_agents: list[str], rubric_ids: set[str], confirmed=None,
                  as_of: date | None = None) -> list[str]:
    """confirmed: the CONFIRMED Scorecard (after review). Controls that rely on an unconfirmed item are flagged."""
    as_of = as_of or reg.as_of
    points = {i.id: (i.points, i.status) for i in confirmed.items} if confirmed is not None else {}
    problems: list[str] = []
    for f in reg.failure_modes:
        if f.agent not in fleet_agents:
            problems.append(f"RISK-008 {f.id}: agent {f.agent!r} isn't in the fleet")
        if f.priority == "High" and not f.action and not f.acceptance:
            problems.append(f"RISK-001 {f.id}: High priority with no action and no acceptance")
        if f.priority == "Medium" and not f.action and not f.acceptance:
            problems.append(f"RISK-010 {f.id}: Medium priority with no action and no acceptance")
        if f.acceptance:
            if f.priority == "High" and not any(b in f.acceptance.by.lower() for b in BOARD):
                problems.append(f"RISK-002 {f.id}: a High risk can only be accepted by the board or risk committee, "
                                f"not {f.acceptance.by}")
            if person(f.acceptance.by) == person(f.owner):
                problems.append(f"RISK-003 {f.id}: accepted by its own risk owner")
            if f.acceptance.expires < as_of:
                problems.append(f"RISK-004 {f.id}: acceptance expired {f.acceptance.expires}")
        if f.action and f.action.due < as_of:
            problems.append(f"RISK-005 {f.id}: action overdue since {f.action.due}")
        for c in f.controls:
            if c.rubric not in rubric_ids:
                problems.append(f"RISK-006 {f.id}: control cites unknown rubric item {c.rubric}")
            elif points and not points[c.rubric][0]:
                problems.append(f"RISK-007 {f.id}: rated assuming control {c.rubric}, which is "
                                f"{points[c.rubric][1]} after review; re-rate or fix the control")
        if f.s >= 9 and not f.controls:
            problems.append(f"RISK-009 {f.id}: severity {f.s} with no control at all")
    return problems


def render_register(rows: list[FailureMode]) -> str:
    lines = ["| ID | Step | Failure mode | S | O | D | RPN | Priority | Controls | Treatment |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for f in rows:
        controls = ", ".join(c.rubric for c in f.controls) or "(none)"
        lines.append(f"| {f.id} | {f.step} | {f.failure_mode} | {f.s} | {f.o} | {f.d} | {f.rpn} | **{f.priority}** "
                     f"| {controls} | {f.treatment} |")
    return "\n".join(lines)
