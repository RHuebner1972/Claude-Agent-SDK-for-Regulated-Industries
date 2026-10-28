"""A small, readable MODEL of the Agent SDK's documented permission flow, for lessons and offline tests.

It is not the SDK: the real flow also handles settings files, ask rules from settings.json, file-path
rules and more. It follows the documented order so you can reason about a configuration on paper:

    1 hooks  ->  2 deny rules (disallowed_tools)  ->  3 ask rules  ->  4 permission mode
             ->  5 allow rules (allowed_tools)  ->  6 can_use_tool callback (skipped and denied in dontAsk)
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Callable, Literal


@dataclass(frozen=True)
class PermissionOutcome:
    decision: Literal["allow", "deny"]
    stage: str

    def __str__(self) -> str:
        return f"{self.decision.upper():5} at {self.stage}"


def _listed(tool: str, rules: tuple[str, ...] | list[str]) -> bool:
    return any(tool == r or fnmatch(tool, r) or tool.startswith(r + "__") for r in rules)


def permission_flow(
    tool: str,
    *,
    mode: Literal["default", "dontAsk", "bypassPermissions"] = "default",
    allowed_tools: tuple[str, ...] | list[str] = (),
    disallowed_tools: tuple[str, ...] | list[str] = (),
    ask_rules: tuple[str, ...] | list[str] = (),
    hook: Callable[[str], Literal["allow", "deny", "pass"]] | None = None,
    can_use_tool: Callable[[str], bool] | None = None,
) -> PermissionOutcome:
    hook_says = hook(tool) if hook else "pass"
    if hook_says == "deny":
        return PermissionOutcome("deny", "1 PreToolUse hook")
    if _listed(tool, disallowed_tools):
        return PermissionOutcome("deny", "2 deny rule (disallowed_tools)")
    asks = _listed(tool, ask_rules)
    if not asks:
        if hook_says == "allow":
            return PermissionOutcome("allow", "1 hook allow (after deny/ask rules)")
        if mode == "bypassPermissions":
            return PermissionOutcome("allow", "4 mode bypassPermissions")
        if _listed(tool, allowed_tools):
            return PermissionOutcome("allow", "5 allow rule (allowed_tools)")
    if mode == "dontAsk":
        return PermissionOutcome("deny", "6 dontAsk: never prompts")
    if can_use_tool is None:
        return PermissionOutcome("deny", "6 no can_use_tool callback")
    return PermissionOutcome("allow" if can_use_tool(tool) else "deny", "6 can_use_tool callback")
