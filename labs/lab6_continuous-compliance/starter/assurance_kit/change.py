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
    # TODO 4: for each agent, the findings that block it ([] = under control).
    # fp = agent.fingerprint(); approved = records for this agent with to_fingerprint == fp and status "approved".
    # CHG-001 none approved: f"CHG-001 {agent.name} is running {fp}, which no approved change record covers ..."
    # For each approved record r:
    #   CHG-002 r.revalidation.result != "passed"
    #   CHG-003 (r.category == "significant" or "model" in r.changed) and (fewer than 2 distinct approver names
    #           or agent.owner not among the approval roles)
    #   CHG-004 r.category == "predetermined" and (any changed field not in changes.plans[agent.name], or "model")
    # Start each finding with its code. Return {agent.name: findings}.
    raise NotImplementedError("Lab 6: check_change_control")


def main() -> None:
    fleet, changes = load_fleet(), load_changes()
    for name, findings in check_change_control(fleet, changes).items():
        print(f"  {name:17} {fleet.get(name).fingerprint()}  {'OK' if not findings else findings[0]}")


if __name__ == "__main__":
    main()
