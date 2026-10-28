"""AI system inventory (M11-L01): one entry per agent, owned by a named person, joined with what the code knows.

The inventory holds the judgments only people can make (purpose, decision role, who is affected, oversight,
classifications, assessments). Facts a machine can read (risk tier, model, tools, fingerprint, deployment path,
regimes, the latest change record) are never copied into it: they're joined in from the fleet manifest, the
deployment manifest, the regulatory map and the change log, so they can't go stale.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

POLICIES = Path(__file__).parent / "policies"
INVENTORY_PATH = POLICIES / "inventory.yaml"
PERSON = r"^[A-Z]\. [A-Z][A-Za-z'\-]+, .{3,}$"          # "D. Okafor, BSA Officer": a person, then their role

AssessmentKind = Literal["AIIA", "FMEA", "HIPAA-SRA", "DPIA", "FRIA"]
DecisionRole = Literal["informs", "recommends", "decides", "acts"]

# Course policy: which assessments every production agent needs, and which regimes add one. Your organization's
# AI policy sets its own list; FRIA (EU AI Act Art. 27) applies only to the deployers the article names.
REQUIRED: dict[str, list[str]] = {"*": ["AIIA", "FMEA"], "HIPAA": ["HIPAA-SRA"], "GDPR": ["DPIA"]}


def person(text: str) -> str:
    """'D. Okafor, BSA Officer' -> 'D. Okafor'."""
    return text.split(",", 1)[0].strip()


class Classification(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    scheme: str
    result: str = Field(min_length=10)
    by: str = Field(pattern=PERSON)


class Assessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: AssessmentKind
    id: str
    date: date
    reviewer: str = Field(pattern=PERSON)
    outcome: str = Field(min_length=10)


class SystemEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    business_owner: str = Field(pattern=PERSON)
    technical_owner: str = Field(pattern=PERSON)
    purpose: str = Field(min_length=20)
    decision_role: DecisionRole
    affected: str = Field(min_length=10)
    human_oversight: str = Field(min_length=10)
    data: list[str] = Field(min_length=1)
    lifecycle: Literal["pilot", "production", "retired"]
    in_production_since: date | None = None
    classifications: list[Classification] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)

    def latest(self, kind: str) -> Assessment | None:
        found = [a for a in self.assessments if a.kind == kind]
        return max(found, key=lambda a: a.date) if found else None


class Inventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    as_of: date
    review_interval_days: dict[int, int]
    systems: dict[str, SystemEntry]

    @model_validator(mode="after")
    def _intervals(self) -> Inventory:
        missing = sorted({1, 2, 3, 4} - set(self.review_interval_days))
        if missing:
            raise ValueError(f"review_interval_days needs every risk tier; missing {missing}")
        return self

    def get(self, name: str) -> SystemEntry:
        if name not in self.systems:
            raise KeyError(f"{name} is not in the AI system inventory")
        return self.systems[name]


def load_inventory(path: str | Path = INVENTORY_PATH) -> Inventory:
    return Inventory.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def required_assessments(regimes: list[str]) -> list[str]:
    kinds = list(REQUIRED["*"])
    for regime in regimes:
        kinds += [k for k in REQUIRED.get(regime, []) if k not in kinds]
    return kinds


def next_review(assessment: Assessment, risk_tier: int, inv: Inventory) -> date:
    return assessment.date + timedelta(days=inv.review_interval_days[risk_tier])


# A change to what the agent IS (its model or its tools) changes its impact: the impact assessment is redone.
REASSESS_ON = {"model", "tools"}


def lint_inventory(inv: Inventory, fleet, regimes: dict[str, list[str]], deployment=None,
                   as_of: date | None = None, changes=None) -> list[str]:
    """Problems an auditor would raise about the inventory itself. Empty list = clean.

    fleet: the production Fleet; regimes: agent -> applicable regimes (RegulatoryMap.applicability);
    deployment: the Deployment manifest (optional); as_of: the date to check review dates against;
    changes: the ChangeLog (optional), to catch impact assessments older than a model or tool change.
    """
    as_of = as_of or inv.as_of
    problems: list[str] = []
    in_fleet = {a.name: a for a in fleet.agents}
    for name in in_fleet.keys() - inv.systems.keys():
        problems.append(f"GOV-001 {name}: runs in the fleet but isn't in the AI inventory (unregistered AI)")
    for name, e in sorted(inv.systems.items()):
        if e.lifecycle == "production" and name not in in_fleet:
            problems.append(f"GOV-002 {name}: inventory says production, but the fleet manifest doesn't run it")
            continue
        if e.lifecycle == "retired" or name not in in_fleet:
            continue
        agent = in_fleet[name]
        if person(e.business_owner) == person(e.technical_owner):
            problems.append(f"GOV-003 {name}: the business owner is also the technical owner; the person "
                            "accountable for the use can't be the person who builds it")
        for kind in required_assessments(regimes.get(name, [])):
            latest = e.latest(kind)
            if latest is None:
                why = "every production agent" if kind in REQUIRED["*"] else \
                    ", ".join(r for r in regimes.get(name, []) if kind in REQUIRED.get(r, []))
                problems.append(f"GOV-004 {name}: no {kind} on file (required for {why})")
            elif next_review(latest, agent.risk_tier, inv) < as_of:
                problems.append(f"GOV-005 {name}: {kind} {latest.id} was due for review on "
                                f"{next_review(latest, agent.risk_tier, inv)} (tier {agent.risk_tier})")
        for a in e.assessments:
            if person(a.reviewer) == person(e.technical_owner):
                problems.append(f"GOV-006 {name}: {a.kind} {a.id} was reviewed by its technical owner")
        if agent.risk_tier >= 4 and e.decision_role in ("decides", "acts"):
            problems.append(f"GOV-007 {name}: a tier-4 agent that {e.decision_role}; course policy keeps a person "
                            "in every tier-4 decision")
        aiia = e.latest("AIIA")
        for c in (changes.records if changes is not None else []):
            if (c.agent == name and c.status == "approved" and REASSESS_ON & set(c.changed) and aiia
                    and date.fromisoformat(c.approvals[-1].date) > aiia.date):
                problems.append(f"GOV-009 {name}: {c.id} changed its {', '.join(sorted(REASSESS_ON & set(c.changed)))} "
                                f"after AIIA {aiia.id} ({aiia.date}); redo the impact assessment")
        if deployment is not None and name not in deployment.agents:
            problems.append(f"GOV-008 {name}: in production with no entry in the deployment manifest")
    return problems
