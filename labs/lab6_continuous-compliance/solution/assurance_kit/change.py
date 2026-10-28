"""Change control for models, prompts, policies and tools (rubric 7.4), with PCCP-style predetermined changes.

Every deployed configuration must match an APPROVED change record whose re-validation passed. Borrowing from FDA's
Predetermined Change Control Plan idea: each agent may declare which kinds of change are pre-planned (described in
advance, with a re-validation protocol). Anything else, and every model change, is a significant change that needs
two approvers including the agent's owner.

    python -m assurance_kit.change            # status: does every agent's fingerprint have a record?
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .fleet import Fleet, load_fleet

CHANGES_PATH = Path(__file__).parent / "policies" / "changes.yaml"
FIELDS = ("model", "prompt_version", "permission_mode", "tools", "controls", "configs")


class Approval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    role: str
    date: str


class Revalidation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    suite: str                                  # e.g. "compliance@<commit>"
    result: Literal["passed", "failed"]
    redteam: str = ""                           # e.g. "13/13 defended"
    date: str


class ChangeRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^CHG-\d{4}$")
    agent: str
    summary: str = Field(min_length=10)
    category: Literal["predetermined", "significant"]
    changed: list[Literal["model", "prompt_version", "permission_mode", "tools", "controls", "configs", "initial"]]
    to_fingerprint: str = Field(pattern=r"^fp:[0-9a-f]{16}$")
    revalidation: Revalidation
    approvals: list[Approval]
    status: Literal["approved", "rejected", "proposed"]


class ChangeLog(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str
    plans: dict[str, list[str]] = Field(default_factory=dict)   # agent -> fields that may change as "predetermined"
    records: list[ChangeRecord]


def load_changes(path: str | Path = CHANGES_PATH) -> ChangeLog:
    return ChangeLog.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def check_change_control(fleet: Fleet, changes: ChangeLog) -> dict[str, list[str]]:
    """For each agent, the findings that block it (empty list = its current configuration is under control)."""
    out: dict[str, list[str]] = {}
    for agent in fleet.agents:
        fp, findings = agent.fingerprint(), []
        records = [r for r in changes.records if r.agent == agent.name and r.to_fingerprint == fp]
        approved = [r for r in records if r.status == "approved"]
        if not approved:
            findings.append(f"CHG-001 {agent.name} is running {fp}, which no approved change record covers "
                            f"(model {agent.model}, prompt {agent.prompt_version})")
        for r in approved:
            if r.revalidation.result != "passed":
                findings.append(f"CHG-002 {r.id}: re-validation did not pass")
            if r.category == "significant" or "model" in r.changed:
                roles = {a.role for a in r.approvals}
                if len({a.name for a in r.approvals}) < 2 or agent.owner not in roles:
                    findings.append(f"CHG-003 {r.id}: a significant change needs two approvers, one of them the "
                                    f"agent owner ({agent.owner})")
            if r.category == "predetermined":
                outside = [f for f in r.changed if f not in changes.plans.get(agent.name, [])]
                if outside or "model" in r.changed:
                    findings.append(f"CHG-004 {r.id}: {outside or ['model']} is outside {agent.name}'s "
                                    f"predetermined change plan")
        out[agent.name] = findings
    return out


def main() -> None:
    fleet, changes = load_fleet(), load_changes()
    for name, findings in check_change_control(fleet, changes).items():
        print(f"  {name:17} {fleet.get(name).fingerprint()}  {'OK' if not findings else findings[0]}")


if __name__ == "__main__":
    main()
