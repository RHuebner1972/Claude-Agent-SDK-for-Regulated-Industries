# M05-L02: The SDK permission stack: allowed/disallowed tools, permission modes and can_use_tool

Module: M05 Pillars 3 & 4, Least Privilege & Policy Engines · Type: Demo

`final/permission_stack.py` traces five tool calls (three complaint tools, `Bash`, `WebFetch`) through three
configurations: `bypassPermissions`, `default` with an allowlist and a `can_use_tool` callback, and the regulated
baseline of `dontAsk` with an explicit allowlist and denylist. Then it adds a PreToolUse hook and shows that a hook
deny wins even under `bypassPermissions`.

The trace uses `sentinel.policy.permission_flow`, a small model of the documented evaluation order
(hooks, deny rules, ask rules, permission mode, allow rules, `can_use_tool`). It is for reasoning on paper; the
SDK itself is the source of truth.

```bash
uv run python lessons/M05-L02_the-sdk-permission-stack-allowed/final/permission_stack.py
```
Code walked through on screen: `src/sentinel/policy/permissions.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
