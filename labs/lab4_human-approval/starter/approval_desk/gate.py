"""The approval gate: hold high-impact tool calls until a person signs, then let exactly that call run once.

Two ways to wait for the human:
  * pre_tool_use (PreToolUse hook): don't wait. Queue the request, then DEFER (the run stops and resumes later
    with the same session) or DENY (the agent carries on and reports what's pending). Works for hours or days.
  * can_use_tool (callback): wait inline for a short time while a reviewer decides in another window.
    If nobody decides in time, the answer is no. A timeout is never an approval.
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Literal

from claude_agent_sdk import HookMatcher, PermissionResultAllow, PermissionResultDeny

from sentinel.policy.enforce import short_name

from .models import ApprovalRequest
from .queue import ApprovalQueue

Evidence = Callable[[str, dict[str, Any]], dict[str, Any]]


def _pre(decision: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                   "permissionDecisionReason": reason}}


def _describe(r: ApprovalRequest) -> str:
    return (f"[APPROVAL-PENDING] {r.request_id}: {r.tool} needs {r.approvals_required} approval(s) from "
            f"{' or '.join(r.allowed_roles())}, due {r.due_at:%Y-%m-%d %H:%M} UTC")


class ApprovalGate:
    def __init__(self, queue: ApprovalQueue, *, user: str, role: str, agent: str,
                 mode: Literal["defer", "deny"] = "defer", evidence: Evidence | None = None,
                 session_id: str | None = None):
        self.queue = queue
        self.user, self.role, self.agent = user, role, agent
        self.mode = mode
        self.evidence = evidence                  # builds the decision-support package the approver sees
        self.session_id = session_id

    def _submit(self, tool: str, tool_input: dict[str, Any], tool_use_id: str | None, session_id: str | None):
        return self.queue.submit(
            tool, tool_input, requested_by=self.user, requester_role=self.role, agent=self.agent,
            session_id=session_id or self.session_id, tool_use_id=tool_use_id,
            rationale=str(tool_input.get("rationale") or tool_input.get("narrative") or tool_input.get("reason") or ""),
            evidence=self.evidence(tool, tool_input) if self.evidence else {})

    # ---- PreToolUse: queue it and pause (defer) or report (deny) ----------------------------------------
    async def pre_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        # TODO 7: the PreToolUse hook.
        # tool = short_name(input_data["tool_name"]); rule = self.queue.policy.rule_for(tool).
        # No rule, or oversight != "in_the_loop" -> return {}.
        # self.queue.sweep(). approved = self.queue.approved_for(tool, tool_input, self.user): if found, consume it and return
        # {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": f"Approved under {id} by ..."}}.
        # call_id = input_data.get("tool_use_id") or tool_use_id; latest = self.queue.latest_for(tool, tool_input, self.user):
        # if rejected or expired -> reason = f"[APPROVAL-{STATUS}] {id}: {why}. Do not retry."; self._log_denial(input_data,
        # call_id, reason, f"{id} {status}"); return _pre("deny", reason).
        # Otherwise request = self._submit(tool, tool_input, call_id, input_data.get("session_id")).
        # defer mode -> return _pre("defer", _describe(request) + ". The run pauses until a person decides.")
        # deny mode  -> reason = _describe(request) + ". Do not retry this call; tell the user it is waiting for approval.";
        #               self._log_denial(input_data, call_id, reason, f"{request.request_id} pending"); return _pre("deny", reason).
        raise NotImplementedError("Lab 4: pre_tool_use")

    def _log_denial(self, input_data: dict[str, Any], call_id: str | None, reason: str, authority: str) -> None:
        """Log the held call with the approval ID, so AuditHooks.observe() doesn't log it again without one."""
        audit = self.queue.audit
        if audit is not None and hasattr(audit, "record_denial"):
            audit.record_denial(input_data["tool_name"], call_id, reason, authority,
                                input_data.get("tool_input", {}), actor_id="approval-gate")

    async def post_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        tool = short_name(input_data["tool_name"])
        rule = self.queue.policy.rule_for(tool)
        if rule is not None and rule.oversight == "on_the_loop":
            self.queue.log_for_review(tool, input_data.get("tool_input", {}), self.user)
        return {}

    # ---- can_use_tool: wait a short time for a reviewer, then say no ------------------------------------
    async def can_use_tool(self, tool_name: str, tool_input: dict[str, Any], context: Any,
                           *, max_wait_s: float = 120.0, poll_s: float = 0.5):
        tool = short_name(tool_name)
        rule = self.queue.policy.rule_for(tool)
        if rule is None or rule.oversight != "in_the_loop":
            return PermissionResultAllow(updated_input=tool_input)
        request = self._submit(tool, tool_input, getattr(context, "tool_use_id", None), None)
        waited = 0.0
        while waited < max_wait_s:
            self.queue.sweep()
            r = self.queue.get(request.request_id)
            if r.status == "approved":
                self.queue.consume(r.request_id)
                return PermissionResultAllow(updated_input=tool_input)
            if r.status in ("rejected", "expired"):
                return PermissionResultDeny(message=f"[APPROVAL-{r.status.upper()}] {r.request_id}", interrupt=False)
            await asyncio.sleep(poll_s)
            waited += poll_s
        return PermissionResultDeny(                       # still undecided: NOT approved
            message=f"[APPROVAL-TIMEOUT] {request.request_id} is still waiting; not approved. It stays in the queue.",
            interrupt=True)

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {"PreToolUse": [HookMatcher(hooks=[self.pre_tool_use])],
                "PostToolUse": [HookMatcher(hooks=[self.post_tool_use])]}
