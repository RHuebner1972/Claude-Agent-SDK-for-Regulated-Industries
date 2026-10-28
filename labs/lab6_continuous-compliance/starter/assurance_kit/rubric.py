"""Score the 40-point rubric from test results and attestations (rubric 7.6). The result is a PROPOSED score:
a reviewer who isn't the author confirms it before anyone relies on it.

An item is
  met (tested)      at least one compliance test evidences it, and every such test passed
  failing           a test evidences it and at least one failed
  met (attested)    no test, but reviewed evidence is on file (attestations.yaml), with a named reviewer and date
  missing           neither (or the control is still planned)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

POLICIES = Path(__file__).parent / "policies"
RUBRIC_PATH, ATTESTATIONS_PATH = POLICIES / "rubric.yaml", POLICIES / "attestations.yaml"
GENERATED_BY_PACK = {"7.6"}          # the pack itself is the evidence for 7.6


@dataclass
class ItemScore:
    id: str
    pillar: str
    critical: bool
    criterion: str
    status: str                       # "met (tested)" | "failing" | "met (attested)" | "missing"
    points: int
    evidence: list[str] = field(default_factory=list)


@dataclass
class Scorecard:
    items: list[ItemScore]

    @property
    def score(self) -> int:
        return sum(i.points for i in self.items)

    @property
    def critical_met(self) -> bool:
        return all(i.points for i in self.items if i.critical)

    @property
    def rating(self) -> str:
        if not self.critical_met or self.score < 30:
            return "Not production-ready"
        return "Audit-ready" if self.score >= 36 else "Conditionally ready"

    def by_pillar(self) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = {}
        for i in self.items:
            out.setdefault(i.pillar, [0, 0])
            out[i.pillar][0] += i.points
            out[i.pillar][1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, "out_of": len(self.items), "critical_met": self.critical_met,
                "rating": self.rating, "by_pillar": self.by_pillar(), "items": [asdict(i) for i in self.items]}


def load_rubric(path: str | Path = RUBRIC_PATH) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_attestations(path: str | Path = ATTESTATIONS_PATH) -> dict[str, dict]:
    return {a["item"]: a for a in yaml.safe_load(Path(path).read_text(encoding="utf-8"))["attestations"]}


def score(results: dict, attestations: dict[str, dict] | None = None, rubric: dict | None = None,
          pack_built: bool = True) -> Scorecard:
    # TODO 7: a PROPOSED score for each rubric item (see the module docstring).
    # Index results["results"] by control id. For each rubric item it:
    #   tests exist        -> "met (tested)" if every outcome is "passed", else "failing";
    #                         evidence = [f"{OUTCOME}: {test}" ...]
    #   it in GENERATED_BY_PACK and pack_built -> "met (tested)", evidence ["this evidence pack: ..."]
    #   attestation status "on_file" WITH a reviewer and a date -> "met (attested)",
    #                         evidence [f"{artifact} (reviewed by {reviewer}, {date})"]  (no reviewer: not evidence)
    #   otherwise                             -> "missing" (evidence: the planned artifact, or "no evidence")
    # points = 1 for any "met ..." status, else 0. Return Scorecard([...ItemScore...]).
    raise NotImplementedError("Lab 6: score")
