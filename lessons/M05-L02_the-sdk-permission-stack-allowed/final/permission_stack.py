"""
M05-L02: the same five tool calls under three agent configurations, traced through the SDK permission flow.

    uv run python lessons/M05-L02_the-sdk-permission-stack-allowed/final/permission_stack.py

Uses sentinel.policy.permission_flow, a readable model of the documented order:
hooks -> deny rules -> ask rules -> permission mode -> allow rules -> can_use_tool.
"""
from __future__ import annotations

from claude_agent_sdk import ClaudeAgentOptions

from sentinel.policy import permission_flow

C = "mcp__complaints__"
CALLS = [C + "get_complaint", C + "add_investigation_note", C + "close_complaint", "Bash", "WebFetch"]

CONFIGS = {
    # 1. The demo-day agent: everything on, no questions asked.
    "A  bypassPermissions": dict(mode="bypassPermissions"),
    # 2. Allowlist plus a callback: unlisted tools reach can_use_tool, which here says no to writes.
    "B  default + allowlist + can_use_tool": dict(
        mode="default", allowed_tools=[C + "get_complaint", C + "list_complaints"],
        can_use_tool=lambda tool: tool.endswith("add_investigation_note")),
    # 3. The regulated baseline: explicit allowlist, explicit denylist, and nothing else ever.
    "C  dontAsk + allowlist + denylist": dict(
        mode="dontAsk", allowed_tools=[C + "get_complaint", C + "list_complaints", C + "add_investigation_note"],
        disallowed_tools=["Bash", "WebFetch", "Write", "Edit"]),
}


def main() -> None:
    for name, cfg in CONFIGS.items():
        print(f"\n{name}")
        for tool in CALLS:
            print(f"  {tool:42} {permission_flow(tool, **cfg)}")

    # A hook runs FIRST, for every call, whatever the mode. Even bypassPermissions can't skip a hook deny.
    print("\nA + a PreToolUse hook that denies close_complaint")
    hook = lambda tool: "deny" if tool.endswith("close_complaint") else "pass"  # noqa: E731
    for tool in CALLS:
        print(f"  {tool:42} {permission_flow(tool, mode='bypassPermissions', hook=hook)}")

    # The real options object for configuration C. tools=[] removes the built-in tools from the model's view.
    options = ClaudeAgentOptions(
        tools=[], permission_mode="dontAsk",
        allowed_tools=[C + "get_complaint", C + "list_complaints", C + "add_investigation_note"],
        disallowed_tools=["Bash", "WebFetch", "Write", "Edit"], setting_sources=[])
    print(f"\nConfiguration C as ClaudeAgentOptions: mode={options.permission_mode}, "
          f"allowed={len(options.allowed_tools)}, disallowed={options.disallowed_tools}")


if __name__ == "__main__":
    main()
