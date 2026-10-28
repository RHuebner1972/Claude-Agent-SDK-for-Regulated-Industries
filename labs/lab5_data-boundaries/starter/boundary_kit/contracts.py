"""Typed handoff contracts: the only shape data may take when it crosses a boundary upward (rubric 6.2).

enforce_contract() parses what a subagent returned, keeps ONLY the contract's fields (everything else is stripped
and named in the result), validates them, and scans every text value for controlled content. Anything that can't
be parsed, doesn't validate, or still contains controlled content is rejected: fail closed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .markings import scan


class ChangeImpactSummary(BaseModel):
    """ENG-FORM-7: what the CCB may know about a controlled engineering change. No technical data."""
    model_config = ConfigDict(extra="forbid")
    form: Literal["ENG-FORM-7"] = "ENG-FORM-7"
    ecr_id: str = Field(pattern=r"^ECR-\d{4}$")
    program: str
    change_class: Literal["Class I", "Class II"]
    recommendation: Literal["approve", "approve_with_conditions", "reject", "needs_more_data"]
    schedule_impact_days: int = Field(ge=0, le=365)
    cost_impact_band: Literal["<10k", "10k-100k", ">100k"]
    affected_assembly_count: int = Field(ge=0)
    requires_customer_approval: bool
    rationale: str = Field(min_length=20, max_length=400)


CONTRACTS: dict[str, type[BaseModel]] = {"ChangeImpactSummary": ChangeImpactSummary}


@dataclass
class HandoffResult:
    ok: bool
    contract: str
    payload: dict[str, Any] | None = None
    stripped: list[str] = field(default_factory=list)     # field NAMES removed, never their values
    findings: list[str] = field(default_factory=list)
    error: str = ""

    def text(self) -> str:
        if self.ok:
            return json.dumps(self.payload, indent=1)
        return f"[BND-002] Handoff rejected ({self.contract}): {self.error or '; '.join(self.findings)}"


def _extract_json(raw: str) -> dict[str, Any]:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the subagent's result")
    data = json.loads(raw[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("handoff must be a JSON object")
    return data


def enforce_contract(raw: str, contract: type[BaseModel], canaries: Iterable[str] = ()) -> HandoffResult:
    # TODO 6: the handoff contract. Fail closed: anything you can't validate is rejected.
    # name = contract.__name__. data = _extract_json(raw); on ValueError/JSONDecodeError return
    #     HandoffResult(False, name, error=f"not a valid {name}: {exc}").
    # allowed = set(contract.model_fields); stripped = sorted(keys in data that are NOT allowed)   <- removed, not passed on
    # model = contract.model_validate({only the allowed keys}); on ValidationError return HandoffResult(False, name,
    #     stripped=stripped, error=f"invalid {name} (loc: msg; ...)").
    # payload = model.model_dump(mode="json"); findings = sorted(set of scan(v, canaries) over every str value).
    # findings -> HandoffResult(False, name, stripped=stripped, findings=findings,
    #                           error="controlled content in an allowed field: " + "; ".join(findings)).
    # Otherwise HandoffResult(True, name, payload=payload, stripped=stripped).
    raise NotImplementedError("Lab 5: enforce_contract")
