"""Route audit events to the log for the boundary they happened in (rubric 6.3, 6.5).

A subagent's tool calls carry agent_type in their hook input. Calls from a cleared subagent go to its enclave's
own audit log; everything else goes to the general log. The general log records a contract-bound subagent's raw
result only as a hash: the readable version stays in the enclave.
"""
from __future__ import annotations

from typing import Any

from claude_agent_sdk import HookMatcher

from sentinel.audit import Actor, AuditHooks
from sentinel.audit.redact import fingerprint, response_text
from sentinel.policy.enforce import short_name

from .guard import AGENT_TOOLS


class RoutingAuditHooks:
    def __init__(self, general: AuditHooks, enclaves: dict[str, AuditHooks], contract_bound: set[str] = frozenset()):
        self.general = general
        self.enclaves = enclaves                  # agent_type -> that boundary's AuditHooks
        self.contract_bound = set(contract_bound)

    def _for(self, input_data: dict[str, Any] | None = None, agent_type: str | None = None) -> AuditHooks:
        name = agent_type or (input_data or {}).get("agent_type")
        return self.enclaves.get(name, self.general) if name else self.general

    def _redact_handoff(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """The general log gets a hash of what the subagent said, not the words."""
        if short_name(input_data["tool_name"]) not in AGENT_TOOLS:
            return input_data
        target = input_data.get("tool_input", {}).get("subagent_type", "")
        if target not in self.contract_bound:
            return input_data
        raw = response_text(input_data.get("tool_response"))
        held = {"content": [{"type": "text", "text": f"[subagent result held in {target}'s enclave log; "
                                                    f"sha256={fingerprint(raw)}]"}]}
        return {**input_data, "tool_response": held}

    async def on_prompt(self, input_data, tool_use_id, context):
        return await self._for(input_data).on_prompt(input_data, tool_use_id, context)

    async def on_pre_tool(self, input_data, tool_use_id, context):
        return await self._for(input_data).on_pre_tool(input_data, tool_use_id, context)

    async def on_post_tool(self, input_data, tool_use_id, context):
        target = input_data.get("tool_input", {}).get("subagent_type", "")
        if short_name(input_data["tool_name"]) in AGENT_TOOLS and target in self.enclaves:
            await self.enclaves[target].on_post_tool(input_data, tool_use_id, context)   # readable copy, inside
        return await self._for(input_data).on_post_tool(self._redact_handoff(input_data), tool_use_id, context)

    async def on_tool_failure(self, input_data, tool_use_id, context):
        return await self._for(input_data).on_tool_failure(input_data, tool_use_id, context)

    async def on_stop(self, input_data, tool_use_id, context):
        return await self.general.on_stop(input_data, tool_use_id, context)

    def observe(self, message: Any) -> None:
        self.general.observe(message)
        for enclave in self.enclaves.values():      # sign each enclave log's head at the end of the run, too
            enclave.store.checkpoint()

    def record_denial(self, tool_name, tool_use_id, reason, authority, tool_input=None, actor_id="policy-engine",
                      agent_type: str | None = None):
        return self._for(agent_type=agent_type).record_denial(tool_name, tool_use_id, reason, authority, tool_input,
                                                              actor_id=actor_id)

    def record(self, event_type: str, actor: Actor, agent_type: str | None = None, **fields):
        return self._for(agent_type=agent_type).record(event_type, actor, **fields)

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {"UserPromptSubmit": [HookMatcher(hooks=[self.on_prompt])],
                "PreToolUse": [HookMatcher(hooks=[self.on_pre_tool])],
                "PostToolUse": [HookMatcher(hooks=[self.on_post_tool])],
                "PostToolUseFailure": [HookMatcher(hooks=[self.on_tool_failure])],
                "Stop": [HookMatcher(hooks=[self.on_stop])]}
