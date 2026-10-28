"""The Regulatory Mapping Framework as executable data (M09): clause -> pillar -> control -> code -> test -> evidence.

The map lives in policies/regulatory_map.yaml. This module
  - validates it with Pydantic (a row that doesn't name a pillar, a control and its evidence won't load),
  - lints it against the repo and the rubric (code paths exist, rubric items exist, every row has an owner),
  - traces each clause to its live status by joining the rubric scorecard and the compliance suite's results.

The test column is never typed by hand: a row names rubric items, and the tests come from whatever the suite
tagged with those items in the latest run. Rename or delete a test and the row turns into a gap on its own.

    python -m sentinel.evidence trace --regime HIPAA
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .rubric import POLICIES, Scorecard, load_rubric

MAP_PATH = POLICIES / "regulatory_map.yaml"
REPO = Path(__file__).resolve().parents[3]
Pillar = Literal["P1", "P2", "P3", "P4", "P5", "P6", "P7"]
PILLARS = {"P1": "Traceability", "P2": "Data Protection", "P3": "Least Privilege", "P4": "Policy Enforcement",
           "P5": "Human Oversight", "P6": "Data Boundaries", "P7": "Continuous Assurance"}


class Regime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str
    source: str
    industry: str


class Mapping(BaseModel):
    """One clause, mapped. Every field is something an auditor or engineer will ask for."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    regime: str
    citation: str = Field(min_length=3)
    requirement: str = Field(min_length=10)
    pillar: Pillar
    control: str = Field(min_length=10)
    rubric: list[str] = Field(default_factory=list)
    code: list[str] = Field(default_factory=list)
    evidence: str = Field(min_length=3)
    owner: str = ""
    note: str = ""

    @field_validator("rubric")
    @classmethod
    def _item_ids(cls, v: list[str]) -> list[str]:
        bad = [i for i in v if not re.fullmatch(r"[1-7]\.[1-6]", i)]
        if bad:
            raise ValueError(f"not rubric item ids: {bad}")
        return v

    @model_validator(mode="after")
    def _someone_answers_for_it(self) -> "Mapping":
        if not self.rubric and not self.owner:
            raise ValueError(f"{self.id}: a row the rubric doesn't score must name an owner")
        return self


class RegulatoryMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    name: str
    version: str
    as_of: str
    regimes: dict[str, Regime]
    applicability: dict[str, list[str]] = Field(default_factory=dict)     # agent -> regimes that apply
    mappings: list[Mapping]

    @model_validator(mode="after")
    def _consistent(self) -> "RegulatoryMap":
        dupes = [k for k, n in Counter(m.id for m in self.mappings).items() if n > 1]
        unknown = sorted(({m.regime for m in self.mappings} | {r for rs in self.applicability.values() for r in rs})
                         - set(self.regimes))
        if dupes or unknown:
            raise ValueError(f"duplicate ids {dupes}; rows for undeclared regimes {unknown}")
        return self

    def regimes_for(self, agent: str) -> list[str]:
        if agent not in self.applicability:
            raise KeyError(f"no applicability decision recorded for {agent!r}: scope it with compliance first")
        return self.applicability[agent]

    def rows(self, regime: str | None = None) -> list[Mapping]:
        if regime and regime not in self.regimes:
            raise KeyError(f"unknown regime {regime!r}; choose from {sorted(self.regimes)}")
        return [m for m in self.mappings if regime in (None, m.regime)]


def load_map(path: str | Path = MAP_PATH) -> RegulatoryMap:
    return RegulatoryMap.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def lint(rmap: RegulatoryMap, rubric: dict | None = None, repo: Path = REPO, fleet_agents: list[str] | None = None
         ) -> list[str]:
    """What a reviewer would catch: dead code links, unknown rubric items, regimes with no rows, unscoped agents."""
    rubric = rubric or load_rubric()
    known = {i["id"] for i in rubric["items"]}
    problems = []
    for m in rmap.mappings:
        problems += [f"{m.id}: unknown rubric item {i}" for i in m.rubric if i not in known]
        problems += [f"{m.id}: code path not found: {p}" for p in m.code if not (repo / p).exists()]
    problems += [f"regime {r} has no rows" for r in rmap.regimes if not rmap.rows(r)]
    problems += [f"fleet agent {a} has no applicability decision" for a in (fleet_agents or [])
                 if a not in rmap.applicability]
    return problems


Status = Literal["met", "failing", "gap", "owned elsewhere"]


@dataclass
class TraceRow:
    mapping: Mapping
    status: Status
    items: list[tuple[str, str]] = field(default_factory=list)      # (rubric id, item status)
    tests: list[str] = field(default_factory=list)                  # "PASSED: test_name[agent]"
    scoped: bool = False                                            # traced for one agent

    @property
    def how(self) -> str:
        if self.status != "met":
            return self.status
        kinds = {s for _, s in self.items}
        if self.scoped and not self.tests and "met (tested)" in kinds:
            return "met (fleet-level evidence)"     # the rubric item is met, but not by a test of THIS agent
        return "met (tested)" if kinds == {"met (tested)"} else "met (attested)" if kinds == {"met (attested)"} \
            else "met (tested + attested)"


def _tests_by_item(results: dict, agent: str | None = None) -> dict[str, list[str]]:
    """Tests per rubric item; with agent=, that agent's tests plus fleet-wide ones (no agent recorded)."""
    out: dict[str, list[str]] = {}
    for r in results.get("results", []):
        if agent and r.get("agent") not in (agent, None, ""):
            continue
        for c in r["controls"]:
            out.setdefault(c, []).append(f"{r['outcome'].upper()}: {r['test']}")
    return out


def trace(rmap: RegulatoryMap, card: Scorecard, results: dict, regime: str | None = None,
          agent: str | None = None) -> list[TraceRow]:
    """Join each clause to the live status of the rubric items its control scores against.

    A clause is met only if every item it depends on earns its point. One failing item makes it failing; any
    other item without a point (missing, challenged, unconfirmed) makes it a gap. Partial coverage is a gap, not
    a pass: auditors read the weakest link. Pass agent= to keep only the regimes that apply to that agent.
    """
    by_id = {i.id: i for i in card.items}
    tests = _tests_by_item(results, agent)
    scope = set(rmap.regimes_for(agent)) if agent else None
    out = []
    for m in rmap.rows(regime):
        if scope is not None and m.regime not in scope:
            continue
        if not m.rubric:
            out.append(TraceRow(m, "owned elsewhere"))
            continue
        items = [(i, by_id[i].status) for i in m.rubric]
        status: Status = ("failing" if any(s == "failing" for _, s in items)
                          else "gap" if any(not by_id[i].points for i in m.rubric) else "met")
        out.append(TraceRow(m, status, items, [t for i in m.rubric for t in tests.get(i, [])], scoped=agent is not None))
    return out


def coverage(rows: list[TraceRow]) -> dict[str, dict[str, int]]:
    """Per regime: how many clauses are met, failing, gaps or owned outside the agent rubric."""
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        bucket = out.setdefault(r.mapping.regime, {"met": 0, "failing": 0, "gap": 0, "owned elsewhere": 0})
        bucket[r.status] += 1
    return out


def render_trace(rmap: RegulatoryMap, rows: list[TraceRow], regime: str | None = None) -> str:
    """Markdown an auditor can read: one table per regime, clause first, evidence last."""
    lines = [f"# Regulatory trace ({rmap.name} v{rmap.version}, map as of {rmap.as_of})", "",
             "Each clause traces to a pillar, an engineering control, the code that implements it, the tests that "
             "prove it in this run and the artifact in this pack. A clause is met only when every rubric item it "
             "depends on is met. This is a teaching map, not legal advice: confirm applicability with your "
             "compliance partner.", ""]
    for key in ([regime] if regime else list(dict.fromkeys(r.mapping.regime for r in rows))):
        mine = [r for r in rows if r.mapping.regime == key]
        if not mine:
            continue
        reg = rmap.regimes[key]
        cov = coverage(mine)[key]
        lines += [f"## {key}: {reg.title}", f"*{reg.source}* · met {cov['met']}, gaps {cov['gap']}, "
                  f"failing {cov['failing']}, owned elsewhere {cov['owned elsewhere']}", "",
                  "| Clause | Pillar | Control | Code | Tests (this run) | Evidence | Status |",
                  "|---|---|---|---|---|---|---|"]
        for r in mine:
            m = r.mapping
            tests = "<br>".join(r.tests[:3]) + (f"<br>… {len(r.tests) - 3} more" if len(r.tests) > 3 else "")
            status = r.how if r.status != "owned elsewhere" else f"owned by {m.owner}"
            if r.status in ("gap", "failing"):
                status += ": " + ", ".join(f"{i} {s}" for i, s in r.items if not s.startswith("met"))
            lines.append(f"| {m.citation} | {m.pillar} | {m.control} | {'<br>'.join(m.code) or '(none yet)'} | "
                         f"{tests or '(no test in this scope)'} | {m.evidence} | **{status}** |")
        lines.append("")
    return "\n".join(lines)


def matrix(rmap: RegulatoryMap) -> dict[str, dict[str, list[str]]]:
    """Pillar x regime: the citations in each cell. The cheat sheet's grid, generated from the same rows."""
    grid: dict[str, dict[str, list[str]]] = {p: {} for p in PILLARS}
    for m in rmap.mappings:
        grid[m.pillar].setdefault(m.regime, []).append(m.citation)
    return grid
