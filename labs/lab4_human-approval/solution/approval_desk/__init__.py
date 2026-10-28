"""Lab 4 solution: approval_desk (same design as sentinel.approvals, which later modules import). approval gates, a persistent approval queue, segregation of duties,
signed approval records, escalation that never auto-approves, and a tested kill switch.

    queue = ApprovalQueue("approvals.json", policy=policy, signing_key=key, audit=audit)
    gate  = ApprovalGate(queue, user="j.rivera", role="aml_analyst", agent="AML-Triage@1.0.0", mode="defer")
    hooks = merge_hooks(audit.sdk_hooks(), enforcer.sdk_hooks(), gate.sdk_hooks())
"""
from .gate import ApprovalGate
from .killswitch import KillSwitch
from .metrics import review_quality
from .models import ActionRule, ApprovalRequest, OversightPolicy, Signature, Signer, load_oversight
from .queue import ApprovalError, ApprovalQueue
from .simulate import FixedClock
from .records import input_digest, make_signature, record_digest, verify_signature
from .sod import SegregationOfDutiesError, check_segregation

__all__ = ["ActionRule", "ApprovalError", "FixedClock", "ApprovalGate", "ApprovalQueue", "KillSwitch", "ApprovalRequest", "OversightPolicy",
           "SegregationOfDutiesError", "Signature", "Signer", "check_segregation", "input_digest", "load_oversight",
           "make_signature", "record_digest", "review_quality", "verify_signature"]
