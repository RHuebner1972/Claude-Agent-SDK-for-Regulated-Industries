"""RACI for a regulated agent (M11-L06): one accountable role per activity, and independence you can check."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .inventory import POLICIES

RACI_PATH = POLICIES / "raci.yaml"


class Role(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    title: str
    line: int = Field(ge=0, le=3)              # lines of defense; 0 = the board


class RaciActivity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str
    artifact: str
    cells: dict[str, str]
    independent_of: list[str] = Field(default_factory=list)
    assurance: bool = False

    def roles(self, letter: str) -> list[str]:
        return [r for r, v in self.cells.items() if letter in v]


class Raci(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str
    roles: dict[str, Role]
    activities: list[RaciActivity]

    def get(self, activity: str) -> RaciActivity:
        return next(a for a in self.activities if a.id == activity)


def load_raci(path: str | Path = RACI_PATH) -> Raci:
    return Raci.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def lint_raci(raci: Raci) -> list[str]:
    problems: list[str] = []
    ids = {a.id for a in raci.activities}
    for a in raci.activities:
        for role, cell in a.cells.items():
            if role not in raci.roles:
                problems.append(f"RACI-005 {a.id}: unknown role {role!r}")
            if cell not in ("R", "A", "C", "I", "AR"):
                problems.append(f"RACI-006 {a.id}: {role} has {cell!r}; use R, A, C, I or AR")
        if len(a.roles("A")) != 1:
            problems.append(f"RACI-001 {a.id}: needs exactly one A, has {a.roles('A') or 'none'}")
        if not a.roles("R"):
            problems.append(f"RACI-002 {a.id}: nobody does the work (no R)")
        for other in a.independent_of:
            if other not in ids:
                problems.append(f"RACI-005 {a.id}: independent_of unknown activity {other!r}")
                continue
            doers = set(raci.get(other).roles("R")) & (set(a.roles("R")) | set(a.roles("A")))
            if doers:
                problems.append(f"RACI-003 {a.id}: {', '.join(sorted(doers))} also does '{other}'; "
                                "it can't check its own work")
        if not a.assurance:
            third = [r for r in a.roles("R") + a.roles("A") if r in raci.roles and raci.roles[r].line == 3]
            if third:
                problems.append(f"RACI-004 {a.id}: internal audit is R or A; the third line can't audit work it does")
    return problems


def render_raci(raci: Raci) -> str:
    keys = list(raci.roles)
    lines = ["| Activity | " + " | ".join(raci.roles[k].title for k in keys) + " | Artifact |",
             "|---|" + "---|" * len(keys) + "---|"]
    for a in raci.activities:
        lines.append(f"| {a.name} | " + " | ".join(a.cells.get(k, "") for k in keys) + f" | {a.artifact} |")
    return "\n".join(lines)
