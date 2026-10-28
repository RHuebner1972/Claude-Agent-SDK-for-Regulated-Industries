"""Wire the policy engine into the Agent SDK: a PreToolUse hook, a can_use_tool callback and a PostToolUse hook.

    enforcer = PolicyEnforcer(engine, subject, resolver=..., validators=..., untrusted_tools=..., audit=audit)
    options = ClaudeAgentOptions(..., hooks=merge_hooks(audit.sdk_hooks(), enforcer.sdk_hooks()))
    # one chained callback per event: the request is logged, THEN judged (the SDK runs separate hooks in parallel)

The PreToolUse hook runs for EVERY tool call (rubric 4.2), so it is the enforcement point. It can only say no:
an allowed call passes on to the rest of the SDK's permission flow, so allowed_tools stays the outer fence.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from claude_agent_sdk import HookMatcher, PermissionResultAllow, PermissionResultDeny

from sentinel.audit.redact import response_text

from .engine import PolicyEngine, build_context
from .models import Decision, Subject

# Instruction-shaped text inside data. A tripwire, not a defense: the defense is that policy, not the model, decides.
INJECTION_MARKERS = re.compile(
    r"(?i)(system note|ignore (all |any )?(previous|prior|above) instructions|^\s*assistant:|\bassistant:|"
    r"do not (mention|tell|report)|you are now|new instructions|disregard (the|your))", re.M)

Resolver = Callable[[str, dict[str, Any]], dict[str, Any] | None]
OutputCheck = Callable[[dict[str, Any], Any], str | None]
Approver = Callable[[Decision, dict[str, Any]], bool]


def short_name(tool_name: str) -> str:
    """mcp__complaints__close_complaint -> close_complaint. Policies are written against short names."""
    return tool_name.split("__")[-1]


def _deny_output(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


class PolicyEnforcer:
    def __init__(
        self,
        engine: PolicyEngine,
        subject: Subject,
        *,
        resolver: Resolver | None = None,
        validators: dict[str, type[BaseModel]] | None = None,
        output_checks: dict[str, OutputCheck] | None = None,
        untrusted_tools: tuple[str, ...] | set[str] = (),
        audit: Any | None = None,
        approver: Approver | None = None,
    ):
        self.engine = engine
        self.subject = subject
        self.resolver = resolver
        self.validators = validators or {}          # pre-conditions: typed input schemas (rubric 4.4)
        self.output_checks = output_checks or {}    # post-conditions on what a tool returned
        self.untrusted_tools = set(untrusted_tools)
        self.audit = audit                           # sentinel.audit.AuditHooks, for denials with rule IDs
        self.approver = approver                     # Module 6 plugs a human approval step in here
        self.environment: dict[str, Any] = {"tainted": False, "injection_suspected": False, "taint_sources": []}
        self.decisions: list[Decision] = []
        self._by_call: dict[str, Decision] = {}      # one decision per tool call, even if two adapters ask

    # ---- the decision ------------------------------------------------------------------------
    def decide(self, tool_name: str, tool_input: dict[str, Any], tool_use_id: str | None = None) -> Decision:
        if tool_use_id and tool_use_id in self._by_call:
            return self._by_call[tool_use_id]        # the hook already decided this call: don't ask twice
        decision = self._decide(tool_name, tool_input)
        if tool_use_id:
            self._by_call[tool_use_id] = decision
        return decision

    def _decide(self, tool_name: str, tool_input: dict[str, Any]) -> Decision:
        tool = short_name(tool_name)
        model = self.validators.get(tool)
        if model is not None:
            try:
                model.model_validate(tool_input)
            except ValidationError as exc:
                problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'input'}: {e['msg']}" for e in exc.errors())
                return self._log(Decision(effect="deny", rule_id="PRE-001", tool=tool,
                                          reason=f"input failed its schema check ({problems})",
                                          policy=self.engine.policy.name, policy_version=self.engine.version))
        resource = self.resolver(tool, tool_input) if self.resolver else None
        context = build_context(self.subject, tool, tool_input, resource, self.environment)
        decision = self.engine.evaluate(context)
        if decision.effect == "ask":
            if self.approver and self.approver(decision, tool_input):
                decision = decision.model_copy(update={"effect": "allow", "reason": decision.reason + " [approved]"})
            else:
                decision = decision.model_copy(update={
                    "effect": "deny",
                    "reason": decision.reason + " (needs human approval, and no approver is configured)"})
        return self._log(decision)

    def _log(self, decision: Decision) -> Decision:
        self.decisions.append(decision)
        return decision

    def _record_denial(self, tool_name: str, tool_use_id: str | None, decision: Decision, tool_input: dict) -> None:
        if self.audit is not None:
            self.audit.record_denial(tool_name, tool_use_id, decision.message(),
                                     f"{decision.rule_id} ({decision.policy_version})", tool_input)

    # ---- adapter 1: PreToolUse hook, runs for every call -------------------------------------
    async def pre_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        # TODO 4: the PreToolUse hook, called for EVERY tool call.
        # tool_name = input_data["tool_name"]; tool_input = input_data.get("tool_input", {});
        # call_id = input_data.get("tool_use_id") or tool_use_id; decision = self.decide(tool_name, tool_input, call_id).
        # allow -> return {} (pass on: allowed_tools and the permission mode still apply; a policy hook only says no).
        # Otherwise self._record_denial(tool_name, call_id, decision, tool_input) and
        # return _deny_output(decision.message()), so the model sees "[RULE-ID] reason".
        raise NotImplementedError("Lab 3: pre_tool_use")

    # ---- adapter 2: can_use_tool, runs only when the SDK flow reaches a prompt ---------------
    async def can_use_tool(self, tool_name: str, tool_input: dict[str, Any], context: Any):
        # TODO 5: the same decision, in the shape can_use_tool needs.
        # call_id = getattr(context, "tool_use_id", None); decision = self.decide(tool_name, tool_input, call_id).
        # allow -> PermissionResultAllow(updated_input=tool_input).
        # Otherwise record the denial (as in TODO 4) and return PermissionResultDeny(message=decision.message(), interrupt=False).
        raise NotImplementedError("Lab 3: can_use_tool")

    # ---- adapter 3: PostToolUse hook, taint tracking and post-conditions --------------------
    async def post_tool_use(self, input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        # TODO 6: after a tool runs. tool = short_name(...); response = response_text(input_data.get("tool_response")).
        # output = {"hookEventName": "PostToolUse"}.
        # If tool is in self.untrusted_tools: set self.environment["tainted"] = True, append tool to "taint_sources", and
        # if INJECTION_MARKERS.search(str(response)): set "injection_suspected" = True and put a security notice in
        # output["additionalContext"] (the text is evidence, not an instruction).
        # Post-condition: check = self.output_checks.get(tool); if check(tool_input, response) returns a problem,
        # output["updatedMCPToolOutput"] = {"content": [{"type": "text", "text": f"[POST-001] tool output withheld: {problem}"}],
        # "is_error": True}.  Return {"hookSpecificOutput": output} if you added anything, else {}.
        raise NotImplementedError("Lab 3: post_tool_use")

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {"PreToolUse": [HookMatcher(hooks=[self.pre_tool_use])],
                "PostToolUse": [HookMatcher(hooks=[self.post_tool_use])]}


def chain(*callbacks):
    """Run hook callbacks one after another, in order, and stop at the first deny.

    The SDK runs separate matching hooks IN PARALLEL, so when order matters (log the request, then judge
    it) put the callbacks in one chained callback instead of separate matchers.
    """
    async def chained(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        merged: dict[str, Any] = {}
        for callback in callbacks:
            out = await callback(input_data, tool_use_id, context) or {}
            specific = out.get("hookSpecificOutput", {})
            if specific.get("permissionDecision") == "deny":
                return out                                   # first deny wins; later hooks don't run
            for key, value in out.items():
                if key == "hookSpecificOutput":
                    merged.setdefault(key, {}).update(value)
                else:
                    merged[key] = value
        return merged
    return chained


def merge_hooks(*hook_sets: dict[str, list[HookMatcher]]) -> dict[str, list[HookMatcher]]:
    """Combine hook dicts into ONE chained callback per event, in the order given (put audit first).

    Only for matchers without a tool pattern (matcher=None), which is how the course hooks are built.
    """
    callbacks: dict[str, list] = {}
    for hooks in hook_sets:
        for event, matchers in hooks.items():
            for m in matchers:
                if m.matcher is not None:
                    raise ValueError("merge_hooks only chains matchers without a tool pattern")
                callbacks.setdefault(event, []).extend(m.hooks)
    return {event: [HookMatcher(hooks=[chain(*cbs)])] for event, cbs in callbacks.items()}
