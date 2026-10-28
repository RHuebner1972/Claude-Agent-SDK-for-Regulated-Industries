"""A persistent approval queue: requests survive restarts, decisions are signed, overdue requests escalate.

Nothing in this file can approve anything by itself. The only path to "approved" is sign() by a person
who passes the segregation-of-duties checks. Time passing only ever escalates or expires a request.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from sentinel.audit import Actor

from .models import ApprovalRequest, OversightPolicy, Signer
from .records import input_digest, make_signature, verify_signature
from .sod import SegregationOfDutiesError, check_segregation


class ApprovalError(RuntimeError):
    pass


class ApprovalQueue:
    def __init__(self, path: str | Path, *, policy: OversightPolicy, signing_key: bytes,
                 clock: Callable[[], datetime] | None = None, audit: Any | None = None,
                 agent_ids: set[str] | frozenset[str] = frozenset()):
        self.path = Path(path)
        self.policy = policy
        self.signing_key = signing_key
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.audit = audit                       # sentinel.audit.AuditHooks: every state change is logged
        self.agent_ids = frozenset(agent_ids)
        self.requests: dict[str, ApprovalRequest] = {}
        self.reviews: list[dict[str, Any]] = []  # on-the-loop actions, sampled for review after the fact
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.requests = {k: ApprovalRequest.model_validate(v) for k, v in data["requests"].items()}
            self.reviews = data.get("reviews", [])

    # ---- persistence: write to a temp file, then replace, so a crash never leaves half a queue ----------
    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        data = {"requests": {k: r.model_dump(mode="json") for k, r in self.requests.items()}, "reviews": self.reviews}
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def _log(self, event_type: str, actor: Actor, request: ApprovalRequest, **fields: Any) -> None:
        if self.audit is not None:
            self.audit.record(event_type, actor, tool_name=request.tool,
                              tool_use_id=request.tool_use_id or request.request_id, **fields)

    def _note(self, request: ApprovalRequest, status: str, by: str, now: datetime, note: str = "") -> None:
        request.history.append({"at": now.isoformat(), "status": status, "by": by, "note": note})
        request.status = status  # type: ignore[assignment]

    # ---- requests ---------------------------------------------------------------------------------------
    def submit(self, tool: str, tool_input: dict[str, Any], *, requested_by: str, requester_role: str, agent: str,
               session_id: str | None = None, tool_use_id: str | None = None, rationale: str = "",
               evidence: dict[str, Any] | None = None) -> ApprovalRequest:
        rule = self.policy.rule_for(tool)
        if rule is None or rule.oversight != "in_the_loop":
            raise ApprovalError(f"{tool} does not need approval under {self.policy.name}")
        digest = input_digest(tool, tool_input)
        for r in self.requests.values():             # the resumed SDK call fires again: don't open a duplicate
            if r.input_sha256 == digest and r.requested_by == requested_by and r.is_open:
                return r
        now = self.clock()
        request = ApprovalRequest(
            request_id=f"APR-{len(self.requests) + 1:06d}", tool=tool, tool_input=tool_input, input_sha256=digest,
            requested_by=requested_by, requester_role=requester_role, agent=agent, session_id=session_id,
            tool_use_id=tool_use_id, rationale=rationale, evidence=evidence or {},
            approvals_required=rule.approvals_required, approver_roles=list(rule.approver_roles),
            must_include_role=rule.must_include_role, meaning_text=rule.meaning, citation=rule.citation,
            created_at=now, due_at=now + timedelta(minutes=rule.timeout_minutes))
        request.history.append({"at": now.isoformat(), "status": "pending", "by": agent, "note": "submitted"})
        self.requests[request.request_id] = request
        self._log("approval.requested", Actor(kind="agent", id=agent), request, outcome="requested",
                  reason=rationale or None,
                  detail={"request_id": request.request_id, "input": tool_input, "due_at": request.due_at.isoformat(),
                          "approver_roles": request.approver_roles, "approvals_required": request.approvals_required})
        self._save()
        return request

    def get(self, request_id: str) -> ApprovalRequest:
        return self.requests[request_id]

    def pending(self, role: str | None = None) -> list[ApprovalRequest]:
        self.sweep()
        return [r for r in self.requests.values() if r.is_open and (role is None or role in r.allowed_roles())]

    def latest_for(self, tool: str, tool_input: dict[str, Any], requested_by: str) -> ApprovalRequest | None:
        digest = input_digest(tool, tool_input)
        hits = [r for r in self.requests.values() if r.input_sha256 == digest and r.requested_by == requested_by]
        return hits[-1] if hits else None

    # ---- decisions --------------------------------------------------------------------------------------
    def sign(self, request_id: str, signer: Signer, meaning: Literal["approve", "reject"], reason: str) -> ApprovalRequest:
        self.sweep()                                  # an overdue request escalates BEFORE anyone signs it
        request = self.requests[request_id]
        if not request.is_open:
            raise ApprovalError(f"{request_id} is {request.status}; it can no longer be signed")
        violations = check_segregation(request, signer, meaning, self.agent_ids)
        if violations:
            self._log("tool.denied", Actor(kind="human", id=signer.user), request, outcome="denied",
                      reason="; ".join(violations), authority="segregation of duties",
                      detail={"request_id": request_id, "attempted": meaning})
            raise SegregationOfDutiesError(request_id, violations)
        now = self.clock()
        signature = make_signature(request, signer, meaning, reason, now, self.signing_key)
        request.signatures.append(signature)
        if meaning == "reject":
            self._note(request, "rejected", signer.user, now, reason)
        elif len(request.approvals) >= request.approvals_required:
            self._note(request, "approved", signer.user, now, reason)
        else:
            request.history.append({"at": now.isoformat(), "status": request.status, "by": signer.user,
                                    "note": f"approval {len(request.approvals)} of {request.approvals_required}"})
        self._log("approval.decided", Actor(kind="human", id=signer.user), request,
                  outcome="allowed" if meaning == "approve" else "denied", reason=reason,
                  authority=f"{request_id} {'approved' if meaning == 'approve' else 'rejected'} by {signer.name} "
                            f"({signer.role}): {request.meaning_text}",
                  detail={"request_id": request_id, "status": request.status, "signed_at": now.isoformat(),
                          "record_sha256": signature.record_sha256, "signature": signature.hmac,
                          "approvals": f"{len(request.approvals)}/{request.approvals_required}"})
        self._save()
        return request

    def sweep(self) -> list[tuple[str, str]]:
        """Escalate or expire overdue requests. Time can only make a request harder to get, never approve it."""
        now, changed = self.clock(), []
        for r in self.requests.values():
            if not r.is_open or now <= r.due_at:
                continue
            rule = self.policy.rule_for(r.tool)
            if rule and rule.escalate_to and r.escalation_level < rule.max_escalations:
                r.escalation_level += 1
                if rule.escalate_to not in r.escalated_to:
                    r.escalated_to.append(rule.escalate_to)
                r.due_at = now + timedelta(minutes=rule.timeout_minutes)
                self._note(r, "escalated", "system", now, f"missed due time; escalated to {rule.escalate_to}")
                reason = f"Not decided in time; escalated to {rule.escalate_to}"
            else:
                self._note(r, "expired", "system", now, "missed due time after escalation; never auto-approved")
                reason = "Expired after escalation; the action will not run"
            self._log("approval.escalated", Actor(kind="system", id="approval-queue"), r, outcome="info",
                      reason=reason, detail={"request_id": r.request_id, "status": r.status,
                                             "due_at": r.due_at.isoformat()})
            changed.append((r.request_id, r.status))
        if changed:
            self._save()
        return changed

    # ---- execution --------------------------------------------------------------------------------------
    def approved_for(self, tool: str, tool_input: dict[str, Any], requested_by: str) -> ApprovalRequest | None:
        """An approved, unused request for exactly this call (same tool, same input), or None."""
        digest = input_digest(tool, tool_input)
        return next((r for r in self.requests.values() if r.status == "approved" and r.input_sha256 == digest
                     and r.requested_by == requested_by), None)

    def consume(self, request_id: str) -> ApprovalRequest:
        """One approval, one execution. A consumed approval can't authorize the same call again."""
        request = self.requests[request_id]
        if request.status != "approved":
            raise ApprovalError(f"{request_id} is {request.status}, not approved")
        now = self.clock()
        request.consumed_at = now
        self._note(request, "consumed", "system", now, "action executed")
        self._save()
        return request

    def verify(self, request_id: str) -> list[tuple[str, bool]]:
        request = self.requests[request_id]
        return [(s.user, verify_signature(request, s, self.signing_key)) for s in request.signatures]

    def log_for_review(self, tool: str, tool_input: dict[str, Any], user: str) -> None:
        self.reviews.append({"at": self.clock().isoformat(), "tool": tool, "input": tool_input, "user": user,
                             "reviewed": False})
        self._save()
