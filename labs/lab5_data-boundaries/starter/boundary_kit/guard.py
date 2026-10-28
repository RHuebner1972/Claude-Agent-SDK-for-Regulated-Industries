"""The boundary guard: enforce agent cards on every tool call, and contracts on every handoff upward.

PreToolUse  (who is calling? from the hook input's agent_type; absent = the orchestrator)
  BND-000 unknown agent             BND-003 delegation to a subagent the card doesn't list
  BND-005 tool not on the card      BND-001 resource marking/export control outside the card's scope
  BND-004 resource from another program (tenant isolation)
PostToolUse on the Agent tool (a subagent's final message, on its way to the orchestrator)
  contract-bound subagent -> enforce_contract(): strip, validate, scan; replace what the orchestrator sees
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

from claude_agent_sdk import HookMatcher

from sentinel.audit import Actor
from sentinel.policy.enforce import short_name

from .cards import CardSet
from .contracts import CONTRACTS, enforce_contract

Resolver = Callable[[str, dict[str, Any]], dict[str, Any] | None]
AGENT_TOOLS = {"Agent", "Task"}             # the Task tool was renamed Agent; both names can appear


def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


class BoundaryGuard:
    def __init__(self, cards: CardSet, *, resolver: Resolver | None = None, canaries: Iterable[str] = (),
                 audit: Any | None = None, enforce_contracts: bool = True):
        self.cards = cards
        self.resolver = resolver
        self.canaries = list(canaries)
        self.audit = audit                       # RoutingAuditHooks: denials land in the caller's own log
        self.enforce_contracts = enforce_contracts
        self.handoffs: list[dict[str, Any]] = []

    def caller(self, input_data: dict[str, Any]) -> str:
        return input_data.get("agent_type") or self.cards.orchestrator

    def check(self, caller: str, tool: str, tool_input: dict[str, Any]) -> str | None:
        """Return a denial reason, or None if the call is inside the caller's boundary."""
        # TODO 2: return a denial reason, or None if the call is inside the caller's boundary. In this order:
        # card = self.cards.get(caller); None -> "[BND-000] {caller!r} has no agent card; unknown agents get nothing".
        # tool in AGENT_TOOLS -> target = tool_input.get("subagent_type", ""); not in card.may_delegate_to ->
        #     "[BND-003] {caller} may not delegate to {target!r} (allowed: ...)"; else None.
        # tool not in card.tools -> "[BND-005] {tool} is not on {caller}'s card".
        # resource = self.resolver(tool, tool_input) if self.resolver else None. If resource:
        #     marking not in card.data_scope -> "[BND-001] {ecr_id} is marked {marking}; {caller} is scoped to {scope}"
        #     export_control == "ITAR" and "ITAR" not in card.export_authorizations -> "[BND-001] ... is ITAR-controlled; ..."
        #     card.programs and resource["program"] not in card.programs -> "[BND-004] {ecr_id} belongs to {program}; {caller} serves {programs}"
        # Otherwise None.
        raise NotImplementedError("Lab 5: check")

    async def pre_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        # TODO 3: the PreToolUse hook.
        # caller = self.caller(input_data)  (agent_type in the hook input, or the orchestrator when absent)
        # tool = short_name(input_data["tool_name"]); reason = self.check(caller, tool, input_data.get("tool_input", {})).
        # None -> return {}.
        # If self.audit: self.audit.record_denial(input_data["tool_name"], input_data.get("tool_use_id") or tool_use_id,
        #     reason, reason.split("]")[0].strip("["), input_data.get("tool_input", {}), actor_id="boundary-guard",
        #     agent_type=input_data.get("agent_type"))      <- the denial lands in the CALLER's log
        # return _deny(reason).
        raise NotImplementedError("Lab 5: pre_tool_use")

    async def post_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        # TODO 7: enforce the contract on a subagent's result before the orchestrator sees it.
        # Only for the Agent/Task tool (short_name in AGENT_TOOLS) and self.enforce_contracts; else return {}.
        # target = tool_input["subagent_type"]; card = self.cards.get(target); no card or no card.handoff_contract -> {}.
        # response = input_data.get("tool_response") or {}; raw = the "text" of every block in response["content"].
        # result = enforce_contract(raw, CONTRACTS[card.handoff_contract], self.canaries)
        # self.handoffs.append({"subagent", "ok", "stripped", "findings", "contract"}).
        # If self.audit: self.audit.record("decision.recorded", Actor(kind="system", id="boundary-guard"), outcome="info",
        #     reason="handoff accepted" | "handoff rejected: " + result.error, authority=f"{contract} contract for {target}",
        #     detail={"stripped_fields": ..., "findings": ...})          <- field NAMES and finding kinds only, never values
        # Return {"hookSpecificOutput": {"hookEventName": "PostToolUse",
        #     "updatedToolOutput": {**response, "content": [{"type": "text", "text": result.text()}]},
        #     "additionalContext": "[BND-HANDOFF] ... validated; fields removed at the boundary: ..." if ok
        #                          else "The subagent's result was withheld at the boundary."}}
        raise NotImplementedError("Lab 5: post_tool_use")

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {"PreToolUse": [HookMatcher(hooks=[self.pre_tool_use])],
                "PostToolUse": [HookMatcher(hooks=[self.post_tool_use])]}
