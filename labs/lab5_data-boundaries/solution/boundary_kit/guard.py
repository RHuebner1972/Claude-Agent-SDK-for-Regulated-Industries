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
        card = self.cards.get(caller)
        if card is None:
            return f"[BND-000] {caller!r} has no agent card; unknown agents get nothing"
        if tool in AGENT_TOOLS:
            target = tool_input.get("subagent_type", "")
            if target not in card.may_delegate_to:
                return f"[BND-003] {caller} may not delegate to {target!r} (allowed: {card.may_delegate_to})"
            return None
        if tool not in card.tools:
            return f"[BND-005] {tool} is not on {caller}'s card"
        resource = self.resolver(tool, tool_input) if self.resolver else None
        if resource:
            marking, export = resource.get("marking", "NONE"), resource.get("export_control")
            if marking not in card.data_scope:
                return f"[BND-001] {resource.get('ecr_id', 'resource')} is marked {marking}; {caller} is scoped to {card.data_scope}"
            if export == "ITAR" and "ITAR" not in card.export_authorizations:
                return f"[BND-001] {resource.get('ecr_id', 'resource')} is ITAR-controlled; {caller} is not authorized for ITAR data"
            if card.programs and resource.get("program") not in card.programs:
                return f"[BND-004] {resource.get('ecr_id', 'resource')} belongs to {resource.get('program')}; {caller} serves {card.programs}"
        return None

    async def pre_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        caller = self.caller(input_data)
        tool = short_name(input_data["tool_name"])
        reason = self.check(caller, tool, input_data.get("tool_input", {}))
        if reason is None:
            return {}
        if self.audit is not None:
            self.audit.record_denial(input_data["tool_name"], input_data.get("tool_use_id") or tool_use_id, reason,
                                     reason.split("]")[0].strip("["), input_data.get("tool_input", {}),
                                     actor_id="boundary-guard", agent_type=input_data.get("agent_type"))
        return _deny(reason)

    async def post_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        if short_name(input_data["tool_name"]) not in AGENT_TOOLS or not self.enforce_contracts:
            return {}
        target = input_data.get("tool_input", {}).get("subagent_type", "")
        card = self.cards.get(target)
        if card is None or not card.handoff_contract:
            return {}
        response = input_data.get("tool_response") or {}
        raw = "\n".join(b.get("text", "") for b in response.get("content", []) if isinstance(b, dict))
        result = enforce_contract(raw, CONTRACTS[card.handoff_contract], self.canaries)
        self.handoffs.append({"subagent": target, "ok": result.ok, "stripped": result.stripped,
                              "findings": result.findings, "contract": result.contract})
        if self.audit is not None:
            self.audit.record("decision.recorded", Actor(kind="system", id="boundary-guard"), outcome="info",
                              reason=("handoff accepted" if result.ok else "handoff rejected: " + result.error),
                              authority=f"{card.handoff_contract} contract for {target}",
                              detail={"stripped_fields": result.stripped, "findings": result.findings})
        note = (f"[BND-HANDOFF] {result.contract} from {target} validated"
                + (f"; fields removed at the boundary: {', '.join(result.stripped)}" if result.stripped else ""))
        return {"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": {**response, "content": [{"type": "text", "text": result.text()}]},
            "additionalContext": note if result.ok else "The subagent's result was withheld at the boundary."}}

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {"PreToolUse": [HookMatcher(hooks=[self.pre_tool_use])],
                "PostToolUse": [HookMatcher(hooks=[self.post_tool_use])]}
