"""Segregation of duties: who may NOT sign, even when they have the right job title."""
from __future__ import annotations

from .models import ApprovalRequest, Signer


class SegregationOfDutiesError(PermissionError):
    def __init__(self, request_id: str, violations: list[str]):
        self.request_id, self.violations = request_id, violations
        super().__init__(f"{request_id}: " + "; ".join(violations))


def check_segregation(request: ApprovalRequest, signer: Signer, meaning: str = "approve",
                      agent_ids: frozenset[str] | set[str] = frozenset()) -> list[str]:
    """Return every rule this signature would break (empty list = allowed)."""
    # TODO 1: return every segregation-of-duties rule this signature would break (empty = allowed).
    # SOD-001 signer.user == request.requested_by (maker-checker).
    # SOD-002 the signer is an agent: role "agent", user in agent_ids, or user == request.agent before the "@".
    # SOD-003 signer.user already signed this request (four eyes = two different people).
    # SOD-004 signer.role not in request.allowed_roles() (approver roles plus any escalation role).
    # SOD-005 approvals only: if request.must_include_role is set and this is the LAST approval needed, at least one
    #         approval must come from that role (or an escalated role); otherwise refuse.
    # SOD-006 signer.user == request.evidence.get("relationship_manager") (conflict of interest).
    # Start each message with its code, e.g. "SOD-001 the requester cannot approve ..." 
    raise NotImplementedError("Lab 4: check_segregation")
