"""M03-L02 starter: fill in the AuditEvent model as we go. Every field answers WHO, WHAT, WHEN, WHY or AUTHORITY."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EventType = Literal[
    "prompt.submitted", "tool.requested", "tool.denied", "tool.completed",
    "tool.failed", "decision.recorded", "agent.stopped", "run.completed",
]


class Actor(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # TODO: kind (human / agent / system) and id


class AgentInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # TODO: name, version, model


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # TODO WHEN:      event_id, timestamp (UTC, timezone-aware), event_type
    # TODO WHO:       actor, on_behalf_of, agent
    # TODO WHAT:      tool_name, tool_use_id, detail, outcome
    # TODO WHY/AUTH:  reason, authority
    # TODO CORRELATE: correlation_id, session_id
    # TODO TAMPER:    seq, prev_hash, hash  (filled by the store in M03-L05)
    # TODO validators: reject naive timestamps; tool events need tool_name + tool_use_id;
    #                  decisions need reason + authority
