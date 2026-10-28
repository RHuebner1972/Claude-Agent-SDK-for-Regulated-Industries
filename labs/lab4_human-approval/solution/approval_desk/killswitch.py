"""The override: one switch, pulled by an authorized person, stops every tool call until it's released.

It's a file on purpose. An operations console, a pager runbook or a person at a terminal can engage it while the
agent is running; the next tool call sees it. Rubric 5.6 asks that it exists AND has been tested: run drill().
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import HookMatcher

from sentinel.audit import Actor

from .models import Signer


class KillSwitch:
    def __init__(self, path: str | Path, *, authorized_roles: tuple[str, ...] = ("bsa_officer", "chief_compliance_officer"),
                 audit: Any | None = None, clock: Callable[[], datetime] | None = None):
        self.path = Path(path)
        self.authorized_roles = authorized_roles
        self.audit = audit
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def state(self) -> dict[str, Any] | None:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else None

    def _check(self, signer: Signer) -> None:
        if signer.role not in self.authorized_roles:
            raise PermissionError(f"{signer.user} ({signer.role}) may not operate the kill switch")

    def _log(self, signer: Signer, reason: str, action: str) -> None:
        if self.audit is not None:
            self.audit.record("decision.recorded", Actor(kind="human", id=signer.user), outcome="info",
                              reason=reason, authority=f"kill switch {action} by {signer.name} ({signer.role})")

    def engage(self, signer: Signer, reason: str) -> None:
        self._check(signer)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"by": signer.user, "role": signer.role, "reason": reason,
                                         "at": self.clock().isoformat()}), encoding="utf-8")
        self._log(signer, reason, "ENGAGED")

    def release(self, signer: Signer, reason: str) -> None:
        self._check(signer)
        self.path.unlink(missing_ok=True)
        self._log(signer, reason, "released")

    async def pre_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        state = self.state
        if not state:
            return {}
        msg = f"[KILL-SWITCH] All agent actions are stopped by {state['by']} ({state['role']}): {state['reason']}"
        if self.audit is not None:                       # log it with its reason, so observe() won't log it again
            self.audit.record_denial(input_data["tool_name"], input_data.get("tool_use_id") or tool_use_id, msg,
                                     f"kill switch engaged by {state['by']}", input_data.get("tool_input", {}),
                                     actor_id="kill-switch")
        return {"continue_": False, "stopReason": msg,                     # stop the whole run, not just this call
                "hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                       "permissionDecisionReason": msg}}

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {"PreToolUse": [HookMatcher(hooks=[self.pre_tool_use])]}
