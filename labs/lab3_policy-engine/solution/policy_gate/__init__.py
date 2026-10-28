"""Lab 3 solution: policy_gate, the policy engine and SDK adapters (same design as sentinel.policy, which later modules import).

    engine   = PolicyEngine.from_file("policies/complaints.yaml")   # versioned policy, separate from prompts
    enforcer = PolicyEnforcer(engine, subject, resolver=..., validators=..., audit=audit)
    hooks    = merge_hooks(audit.sdk_hooks(), enforcer.sdk_hooks())  # every tool call evaluated first
"""
from .engine import PolicyEngine, build_context, load_policy
from .enforce import INJECTION_MARKERS, PolicyEnforcer, chain, merge_hooks, short_name
from .models import Condition, Decision, PolicySet, Rule, Subject
from .permissions import PermissionOutcome, permission_flow

__all__ = ["Condition", "Decision", "INJECTION_MARKERS", "PermissionOutcome", "PolicyEnforcer", "PolicyEngine",
           "PolicySet", "Rule", "Subject", "build_context", "chain", "load_policy", "merge_hooks", "permission_flow",
           "short_name"]
