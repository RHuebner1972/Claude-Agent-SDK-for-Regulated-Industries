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
    v: list[str] = []
    if signer.user == request.requested_by:
        v.append("SOD-001 the requester cannot approve or reject their own request (maker-checker)")
    agent_name = request.agent.split("@")[0]
    if signer.role == "agent" or signer.user in agent_ids or signer.user == agent_name:
        v.append("SOD-002 an AI agent cannot sign; only an authenticated person can")
    if signer.user in {s.user for s in request.signatures}:
        v.append("SOD-003 each signature must come from a different person (four eyes)")
    if signer.role not in request.allowed_roles():
        v.append(f"SOD-004 role {signer.role!r} may not decide {request.tool} (allowed: {request.allowed_roles()})")
    if meaning == "approve" and request.must_include_role:
        roles_signed = {s.role for s in request.approvals}
        last_needed = request.approvals_required - len(request.approvals) == 1
        senior = {request.must_include_role, *request.escalated_to}
        if last_needed and not (roles_signed & senior) and signer.role not in senior:
            v.append(f"SOD-005 one of the approvals must come from {request.must_include_role}")
    if signer.user == request.evidence.get("relationship_manager"):
        v.append("SOD-006 the signer manages this customer relationship (conflict of interest)")
    return v
