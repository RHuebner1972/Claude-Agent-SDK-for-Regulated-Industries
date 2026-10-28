"""Oversight rules, approval requests and electronic signatures, as typed data."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sentinel.audit import content_version

Oversight = Literal["none", "on_the_loop", "in_the_loop"]
Status = Literal["pending", "approved", "rejected", "escalated", "expired", "consumed"]
OPEN = ("pending", "escalated")


class ActionRule(BaseModel):
    """How much human oversight one tool needs, and who may give it."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    tool: str
    oversight: Oversight
    approvals_required: int = Field(0, ge=0, le=3)
    approver_roles: list[str] = Field(default_factory=list)
    must_include_role: str | None = None
    timeout_minutes: int = Field(240, ge=1)
    escalate_to: str | None = None
    max_escalations: int = Field(1, ge=0, le=3)
    meaning: str = ""                       # what an approval signature MEANS (Part 11.50(a)(3))
    citation: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> "ActionRule":
        if self.oversight == "in_the_loop":
            if self.approvals_required < 1 or not self.approver_roles or len(self.meaning) < 20:
                raise ValueError(f"{self.tool}: in_the_loop needs approvals_required, approver_roles and a meaning")
            if self.must_include_role and self.must_include_role not in self.approver_roles:
                raise ValueError(f"{self.tool}: must_include_role must be one of approver_roles")
        return self


class OversightPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    rules: list[ActionRule]

    @field_validator("rules")
    @classmethod
    def _unique(cls, rules: list[ActionRule]) -> list[ActionRule]:
        tools = [r.tool for r in rules]
        if len(tools) != len(set(tools)):
            raise ValueError("each tool may appear once")
        return rules

    def rule_for(self, tool: str) -> ActionRule | None:
        return next((r for r in self.rules if r.tool == tool), None)


def load_oversight(path: str | Path) -> tuple[OversightPolicy, str]:
    text = Path(path).read_text(encoding="utf-8")
    return OversightPolicy.model_validate(yaml.safe_load(text)), content_version(text)


class Signer(BaseModel):
    """The authenticated human about to sign. Comes from your identity provider, never from the agent."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    user: str
    name: str
    role: str
    auth_method: str = "sso+mfa"


class Signature(BaseModel):
    """One electronic signature: who, when, and what it means, linked to the exact record signed."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    user: str
    name: str                                # printed name (11.50(a)(1))
    role: str
    meaning: Literal["approve", "reject"]    # meaning (11.50(a)(3)) ...
    meaning_text: str                        # ... in words the signer saw
    reason: str = Field(min_length=15)       # no empty rubber stamps
    signed_at: datetime                      # date and time (11.50(a)(2))
    auth_method: str
    record_sha256: str                       # links the signature to the record (11.70)
    hmac: str


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(pattern=r"^APR-\d{6}$")
    tool: str
    tool_input: dict[str, Any]
    input_sha256: str
    requested_by: str                        # the human the agent works for
    requester_role: str
    agent: str
    session_id: str | None = None
    tool_use_id: str | None = None
    rationale: str = ""                      # the agent's explanation, shown to the approver
    evidence: dict[str, Any] = Field(default_factory=dict)   # decision support, shown to the approver
    approvals_required: int
    approver_roles: list[str]
    must_include_role: str | None = None
    meaning_text: str
    citation: str | None = None
    created_at: datetime
    due_at: datetime
    status: Status = "pending"
    escalation_level: int = 0
    escalated_to: list[str] = Field(default_factory=list)
    signatures: list[Signature] = Field(default_factory=list)
    consumed_at: datetime | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)

    def record_core(self) -> dict[str, Any]:
        """The fields a signature vouches for. Change any of them after signing and verification fails."""
        return {k: getattr(self, k) for k in ("request_id", "tool", "tool_input", "input_sha256", "requested_by",
                                               "agent", "rationale", "evidence", "meaning_text")}

    def allowed_roles(self) -> list[str]:
        return self.approver_roles + [r for r in self.escalated_to if r not in self.approver_roles]

    @property
    def approvals(self) -> list[Signature]:
        return [s for s in self.signatures if s.meaning == "approve"]

    @property
    def is_open(self) -> bool:
        return self.status in OPEN
