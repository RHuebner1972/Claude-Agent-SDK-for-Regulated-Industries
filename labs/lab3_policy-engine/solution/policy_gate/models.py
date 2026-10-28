"""Policy as typed data: rules, conditions and decisions, validated by Pydantic before they ever run."""
from __future__ import annotations

import re
from fnmatch import fnmatch
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Effect = Literal["allow", "deny", "ask"]
Op = Literal["eq", "ne", "in", "not_in", "contains", "matches", "exists", "missing", "gt", "lt", "len_ge"]
_MISSING = object()


def lookup(context: dict[str, Any], path: str) -> Any:
    """Read 'resource.complainant.email' from nested dicts. Missing keys return a sentinel, not an error."""
    value: Any = context
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


class Condition(BaseModel):
    """One test against the request context, e.g. {field: subject.role, op: in, value: [qa_specialist]}.

    A string value starting with "$" refers to another field: value: $resource.complainant.email
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    field: str = Field(pattern=r"^(subject|tool|input|resource|environment)(\.[A-Za-z0-9_]+)*$")
    op: Op
    value: Any = None

    def matches(self, context: dict[str, Any]) -> bool:
        actual = lookup(context, self.field)
        expected = self.value
        if isinstance(expected, str) and expected.startswith("$"):
            expected = lookup(context, expected[1:])
        if self.op == "exists":
            return actual is not _MISSING and actual is not None
        if self.op == "missing":
            return actual is _MISSING or actual is None
        if actual is _MISSING:
            return False                                   # a condition on a missing field never matches
        if self.op == "eq":
            return actual == expected
        if self.op == "ne":
            return actual != expected
        if self.op == "in":
            return actual in expected
        if self.op == "not_in":
            return actual not in expected
        if self.op == "contains":
            return expected in actual
        if self.op == "matches":
            return re.search(expected, str(actual)) is not None
        if self.op == "gt":
            return actual > expected
        if self.op == "lt":
            return actual < expected
        if self.op == "len_ge":
            return len(actual) >= expected
        raise ValueError(f"unknown op {self.op}")


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^[A-Z]+-\d{3}$")
    description: str = Field(min_length=10)
    effect: Effect
    tools: list[str] = Field(min_length=1, description="Short tool names; fnmatch patterns like 'get_*' or '*'")
    when: list[Condition] = Field(default_factory=list, description="All must match (AND)")
    citation: str | None = None

    def applies_to(self, tool: str) -> bool:
        return any(fnmatch(tool, pattern) for pattern in self.tools)

    def matches(self, context: dict[str, Any]) -> bool:
        return self.applies_to(context["tool"]) and all(c.matches(context) for c in self.when)


class PolicySet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    default_effect: Literal["deny"] = "deny"          # anything not explicitly allowed is denied
    rules: list[Rule]

    @field_validator("rules")
    @classmethod
    def _unique_ids(cls, rules: list[Rule]) -> list[Rule]:
        ids = [r.id for r in rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate rule ids: {sorted(dupes)}")
        return rules


class Subject(BaseModel):
    """WHO is asking: the human the agent acts for, their role and purpose, and the agent itself."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    user: str
    role: str
    purpose: str
    agent: str = "agent"


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)
    effect: Effect
    rule_id: str
    reason: str
    tool: str
    policy: str
    policy_version: str
    matched: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _deny_has_rule(self) -> "Decision":
        if self.effect != "allow" and not self.rule_id:
            raise ValueError("every deny or ask must carry a rule id")
        return self

    def message(self) -> str:
        return f"[{self.rule_id}] {self.reason}"
