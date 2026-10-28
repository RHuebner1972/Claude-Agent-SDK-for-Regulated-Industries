"""Lab 3 starter: policy_gate. TODOs 1-6 are in models.py, engine.py and enforce.py; TODO 7 is in policies/complaints.yaml; TODO 8 is triage_pipeline.py.

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
