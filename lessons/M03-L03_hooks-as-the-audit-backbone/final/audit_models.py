"""The AuditEvent model: one record per thing the agent (or a human) did.

An auditor asks five questions about any action: WHO did it, WHAT happened, WHEN, WHY,
and under what AUTHORITY. Every field below answers one of them, and the validators refuse
to create an event that can't.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"

EventType = Literal[
    "prompt.submitted",   # a human (or upstream system) asked the agent to do something
    "tool.requested",     # the agent asked to call a tool (not yet allowed or run)
    "tool.denied",        # the permission layer refused the call
    "tool.completed",     # the tool ran and returned
    "tool.failed",        # the tool ran and raised / returned an error
    "decision.recorded",  # the agent produced a business decision or recommendation
    "agent.stopped",      # the agent finished its turn; carries the final answer
    "run.completed",      # the SDK's result: turns, cost, terminal reason
    "approval.requested", # an action was held for human approval (Module 6)
    "approval.decided",   # a human signed: approve or reject, with the meaning of the signature
    "approval.escalated", # a request missed its due time and moved up, or expired (never auto-approved)
]

TOOL_EVENTS = {"tool.requested", "tool.denied", "tool.completed", "tool.failed"}


class Actor(BaseModel):
    """WHO acted: a human, the agent itself, or the platform."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["human", "agent", "system"]
    id: str = Field(min_length=1)


def content_version(text: str) -> str:
    """A short, stable version ID for a prompt or policy: change one character and the version changes."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class AgentInfo(BaseModel):
    """WHICH agent, exactly: name, release, pinned model, and the prompt and policy it ran under."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1, description="Version or hash of the system prompt")
    policy_version: str = Field(min_length=1, description="Version or hash of the policy the agent applied")


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # WHEN
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType
    # WHO
    actor: Actor
    on_behalf_of: str = Field(min_length=1, description="The accountable human the agent is working for")
    agent: AgentInfo
    # WHAT
    tool_name: str | None = None
    tool_use_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict, description="Redacted summary; never raw sensitive data")
    outcome: Literal["requested", "allowed", "denied", "success", "error", "info"] = "info"
    # WHY and UNDER WHAT AUTHORITY
    reason: str | None = None
    authority: str | None = Field(default=None, description="Policy rule, approval ID or role that permitted this")
    # CORRELATION
    correlation_id: str = Field(min_length=1, description="One ID for the whole run, across every system it touches")
    session_id: str | None = None
    # TAMPER EVIDENCE (filled in by the store, never by the caller)
    seq: int | None = None
    prev_hash: str | None = None
    hash: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware; naive local times can't be ordered across systems")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _answers_the_auditor(self) -> "AuditEvent":
        if self.event_type in TOOL_EVENTS and not (self.tool_name and self.tool_use_id):
            raise ValueError(f"{self.event_type} needs tool_name and tool_use_id")
        if self.event_type == "tool.denied" and not self.reason:
            raise ValueError("tool.denied needs a reason")
        if self.event_type in ("decision.recorded", "approval.decided") and not (self.reason and self.authority):
            raise ValueError(f"{self.event_type} needs a reason (why) and an authority (which rule or approval)")
        return self
