"""SDK hooks that turn every prompt, tool call, result and final answer into an AuditEvent.

    audit = AuditHooks(store, agent=AgentInfo(...), on_behalf_of="j.chen")
    options = ClaudeAgentOptions(..., hooks=audit.sdk_hooks())
    async for message in query(prompt=task, options=options):
        audit.observe(message)          # records the run result and any permission denials

Hooks run in the SDK's control loop for EVERY tool call, so the agent can't skip them and
the model can't talk its way around them. That is why they, not print(), are the backbone.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from claude_agent_sdk import HookMatcher, ResultMessage

from .models import Actor, AgentInfo, AuditEvent
from .redact import fingerprint, redact, response_text, summarize
from .store import AuditStore

FAIL_CLOSED = "Audit log unavailable: the action was blocked because it could not be recorded."


def new_correlation_id() -> str:
    return f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


class AuditHooks:
    def __init__(
        self,
        store: AuditStore,
        *,
        agent: AgentInfo,
        on_behalf_of: str,
        correlation_id: str | None = None,
        decision_tool: str = "record_recommendation",
        clock: Callable[[], datetime] | None = None,
        redactor: Callable[[Any], Any] = redact,
    ):
        self.store = store
        self.agent = agent
        self.on_behalf_of = on_behalf_of
        self.correlation_id = correlation_id or new_correlation_id()
        self.decision_tool = decision_tool
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.redactor = redactor        # M04 swaps in sentinel.privacy.PrivacyRedactor
        self.session_id: str | None = None
        self._denied_ids: set[str] = set()   # denials already logged by a policy engine (Module 5)

    # ---- building and writing events -------------------------------------------------
    def _emit(self, event_type: str, actor: Actor, **fields: Any) -> AuditEvent:
        event = AuditEvent(
            timestamp=self.clock(),
            event_type=event_type,
            actor=actor,
            on_behalf_of=self.on_behalf_of,
            agent=self.agent,
            correlation_id=self.correlation_id,
            session_id=self.session_id,
            **fields,
        )
        return self.store.append(event)

    @property
    def _agent_actor(self) -> Actor:
        return Actor(kind="agent", id=f"{self.agent.name}@{self.agent.version}")

    def _track_session(self, input_data: dict[str, Any]) -> None:
        self.session_id = input_data.get("session_id") or self.session_id

    # ---- the hook callbacks: signature (input_data, tool_use_id, context) -> dict ------
    async def on_prompt(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        self._track_session(input_data)
        self._emit(
            "prompt.submitted",
            Actor(kind="human", id=self.on_behalf_of),
            detail={"prompt": summarize(self.redactor(input_data.get("prompt", "")), 1000),
                    "transcript_path": input_data.get("transcript_path")},
        )
        return {}

    async def on_pre_tool(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        self._track_session(input_data)
        try:
            self._emit(
                "tool.requested",
                self._agent_actor,
                tool_name=input_data["tool_name"],
                tool_use_id=input_data.get("tool_use_id") or tool_use_id,
                outcome="requested",
                detail={"input": self.redactor(input_data.get("tool_input", {}))},
            )
        except Exception:  # no record, no action: fail closed
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                           "permissionDecision": "deny",
                                           "permissionDecisionReason": FAIL_CLOSED}}
        return {}

    async def on_post_tool(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        self._track_session(input_data)
        tool_name = input_data["tool_name"]
        call_id = input_data.get("tool_use_id") or tool_use_id
        tool_input = input_data.get("tool_input", {})
        response = response_text(input_data.get("tool_response"))
        self._emit(
            "tool.completed",
            self._agent_actor,
            tool_name=tool_name,
            tool_use_id=call_id,
            outcome="success",
            detail={
                "input": self.redactor(tool_input),
                "response_sha256": fingerprint(response),       # proves WHAT the agent saw
                "response_summary": summarize(self.redactor(response)),  # readable, redacted
                "duration_ms": input_data.get("duration_ms"),
            },
        )
        if tool_name.split("__")[-1] == self.decision_tool:
            self._emit(
                "decision.recorded",
                self._agent_actor,
                tool_name=tool_name,
                tool_use_id=call_id,
                outcome="info",
                reason=self.redactor(tool_input.get("rationale") or "(no rationale given)"),
                authority=tool_input.get("policy_rule") or "(no rule cited)",
                detail=self.redactor({k: v for k, v in tool_input.items() if k not in ("rationale", "policy_rule")}),
            )
        return {}

    async def on_tool_failure(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        self._track_session(input_data)
        self._emit(
            "tool.failed",
            self._agent_actor,
            tool_name=input_data["tool_name"],
            tool_use_id=input_data.get("tool_use_id") or tool_use_id,
            outcome="error",
            reason=summarize(self.redactor(input_data.get("error", "")), 500),
            detail={"input": self.redactor(input_data.get("tool_input", {}))},
        )
        return {}

    async def on_stop(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        self._track_session(input_data)
        self._emit(
            "agent.stopped",
            self._agent_actor,
            detail={"final_answer": summarize(self.redactor(input_data.get("last_assistant_message", "")), 2000)},
        )
        return {}

    def record(self, event_type: str, actor: Actor, **fields: Any) -> AuditEvent:
        """Log an event that doesn't come from an SDK hook, such as a human approval (Module 6)."""
        return self._emit(event_type, actor, **fields)

    def record_denial(self, tool_name: str, tool_use_id: str | None, reason: str, authority: str,
                      tool_input: dict[str, Any] | None = None, actor_id: str = "policy-engine") -> AuditEvent:
        """Log a denial made by a policy engine, with the rule that made it (Module 5, rubric 4.3)."""
        call_id = tool_use_id or f"unknown-{uuid.uuid4().hex[:8]}"
        self._denied_ids.add(call_id)
        return self._emit(
            "tool.denied",
            Actor(kind="system", id=actor_id),
            tool_name=tool_name,
            tool_use_id=call_id,
            outcome="denied",
            reason=reason,
            authority=authority,
            detail={"input": self.redactor(tool_input or {})},
        )

    # ---- the message stream: things only the result knows -------------------------------
    def observe(self, message: Any) -> None:
        """Call for every message from query(). Records permission denials and the run result."""
        if not isinstance(message, ResultMessage):
            return
        self.session_id = message.session_id or self.session_id
        for denial in message.permission_denials or []:
            denial = denial if isinstance(denial, dict) else vars(denial)
            if denial.get("tool_use_id") in self._denied_ids:
                continue                      # already logged, with its rule ID, by the policy engine
            self._emit(
                "tool.denied",
                Actor(kind="system", id="permission-layer"),
                tool_name=denial.get("tool_name", "unknown"),
                tool_use_id=denial.get("tool_use_id", "unknown"),
                outcome="denied",
                reason="Not in allowed_tools; denied by permission mode",
                detail={"input": self.redactor(denial.get("tool_input", {}))},
            )
        self._emit(
            "run.completed",
            Actor(kind="system", id="agent-sdk"),
            outcome="error" if message.is_error else "success",
            detail={"subtype": message.subtype, "num_turns": message.num_turns,
                    "total_cost_usd": message.total_cost_usd, "terminal_reason": message.terminal_reason},
        )
        self.store.checkpoint()

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        """Pass to ClaudeAgentOptions(hooks=...). No matcher = every tool, including MCP tools."""
        return {
            "UserPromptSubmit": [HookMatcher(hooks=[self.on_prompt])],
            "PreToolUse": [HookMatcher(hooks=[self.on_pre_tool])],
            "PostToolUse": [HookMatcher(hooks=[self.on_post_tool])],
            "PostToolUseFailure": [HookMatcher(hooks=[self.on_tool_failure])],
            "Stop": [HookMatcher(hooks=[self.on_stop])],
        }
