"""The policy engine: load a versioned YAML policy, evaluate a request context, return a Decision.

Combining algorithm: deny overrides everything; ask turns an allowed call into "needs a human";
and if no allow rule matches, the answer is deny (an ask rule alone never grants anything).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sentinel.audit import content_version

from .models import Decision, PolicySet, Rule, Subject


def load_policy(path: str | Path) -> tuple[PolicySet, str]:
    """Parse and validate a policy file. Returns the PolicySet and a content hash of the exact file."""
    text = Path(path).read_text(encoding="utf-8")
    policy = PolicySet.model_validate(yaml.safe_load(text))
    return policy, content_version(text)


def build_context(subject: Subject, tool: str, tool_input: dict[str, Any], resource: dict | None,
                  environment: dict[str, Any]) -> dict[str, Any]:
    return {"subject": subject.model_dump(), "tool": tool, "input": tool_input,
            "resource": resource or {}, "environment": environment}


class PolicyEngine:
    def __init__(self, policy: PolicySet, content_hash: str = "unversioned"):
        self.policy = policy
        self.content_hash = content_hash

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine":
        return cls(*load_policy(path))

    @property
    def version(self) -> str:
        return f"{self.policy.name}@{self.policy.version} ({self.content_hash})"

    def evaluate(self, context: dict[str, Any]) -> Decision:
        matched: list[Rule] = [r for r in self.policy.rules if r.matches(context)]
        ids = [r.id for r in matched]
        deny = next((r for r in matched if r.effect == "deny"), None)
        allow = next((r for r in matched if r.effect == "allow"), None)
        ask = next((r for r in matched if r.effect == "ask"), None)
        # deny overrides everything; ask adds a human to a call that is otherwise ALLOWED.
        # An ask rule can never grant a tool that no allow rule grants: that would be escalation.
        hit = deny or (ask if allow else None) or allow
        if hit:
            reason = hit.description + (f" ({hit.citation})" if hit.citation else "")
            return Decision(effect=hit.effect, rule_id=hit.id, reason=reason, tool=context["tool"],
                            policy=self.policy.name, policy_version=self.version, matched=ids)
        role = context["subject"].get("role")
        return Decision(effect="deny", rule_id="DEFAULT-DENY",
                        reason=f"no rule allows {context['tool']} for role {role!r}",
                        tool=context["tool"], policy=self.policy.name, policy_version=self.version, matched=ids)
