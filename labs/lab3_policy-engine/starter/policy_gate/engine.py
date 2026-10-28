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
    # TODO 3: read the file as text (utf-8), parse it with yaml.safe_load, validate it with
    # PolicySet.model_validate (a bad file must raise, never half-load), and return (policy, content_version(text)).
    raise NotImplementedError("Lab 3: load_policy")


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
        # TODO 2: the combining algorithm.
        # matched = every rule in self.policy.rules whose rule.matches(context) is True; ids = their rule IDs.
        # deny/allow/ask = the first matching rule with that effect (or None).
        # Any deny wins. Otherwise, if an allow matched: a matching ask wins (needs a human), else the allow.
        # If NO allow matched, an ask alone must not grant anything: fall through to the default.
        # Return Decision(effect=hit.effect, rule_id=hit.id, reason=hit.description + f" ({hit.citation})" if it has one,
        # tool=context["tool"], policy=self.policy.name, policy_version=self.version, matched=ids).
        # No hit: Decision(effect="deny", rule_id="DEFAULT-DENY",
        # reason=f"no rule allows {tool} for role {role!r}", ...). Least privilege means the default is NO.
        raise NotImplementedError("Lab 3: evaluate")
