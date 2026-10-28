"""
M10-L04: sandbox the agent runtime. A hardened container with no network, an egress allowlist at the proxy, a
filesystem guard for file tools, and the SDK's own Bash sandbox as a backstop.

    uv run python lessons/M10-L04_sandboxing-the-agent-runtime-containers/final/sandbox_demo.py
    uv run python -m sentinel.deploy docker aml-triage
"""
from __future__ import annotations

import asyncio
import json

from sentinel.deploy import (EgressPolicy, FsGuard, SandboxProfile, docker_args, lint_profile, load_deployment,
                             sdk_sandbox_settings)

AGENT = "aml-triage"


def main() -> None:
    dep = load_deployment().get(AGENT)
    p = dep.sandbox
    print(f"1. THE CONTAINER for {AGENT}: what `docker run` looks like for this profile")
    args, lines = docker_args(p, AGENT), []
    for tok in args:
        if tok.startswith("-") or not lines or tok == args[-1]:
            lines.append(tok)
        else:
            lines[-1] += " " + tok
    print("   " + " \\\n     ".join(lines))
    print(f"   lint: {lint_profile(p, dep.endpoint) or 'clean'}")

    print("\n2. A PROFILE A REVIEWER WOULD REJECT")
    weak = SandboxProfile.model_validate({**p.model_dump(), "user": "0:0", "read_only_root": False,
                                          "network": "bridge", "egress_allowlist": ["*.com"],
                                          "mounts": [{"source": "~/.aws", "target": "/home/agent/.aws"}]})
    for finding in lint_profile(weak, dep.endpoint):
        print(f"   {finding}")

    print("\n3. EGRESS: the proxy's allowlist decides what leaves")
    egress = EgressPolicy(p.egress_allowlist)
    for url in [f"https://{dep.endpoint}/model/invoke", "https://core-banking.bayside.example/v1/alerts",
                "https://paste.example.net/upload?d=customer-list", "http://core-banking.bayside.example/",
                "https://198.51.100.23/exfil", f"https://{dep.endpoint}.attacker.example/"]:
        d = egress.check(url)
        print(f"   {'ALLOW' if d.allowed else 'DENY '} {url:58} {d.reason}")

    print("\n4. FILES: a PreToolUse guard for Read/Write/Edit/Glob (the SDK sandbox doesn't cover file tools)")
    guard = FsGuard(read_roots=[p.workspace], write_roots=[p.workspace])
    for tool, path in [("Read", "/workspace/alert-7781.json"), ("Write", "/workspace/case-note.md"),
                       ("Read", "/workspace/.env"), ("Read", "/etc/passwd"),
                       ("Write", "/workspace/../home/agent/.bashrc"), ("Glob", "/home/agent/.aws/credentials")]:
        decision, reason = guard.decide(tool, {"file_path": path})
        print(f"   {decision.upper():5} {tool:5} {path:36} {reason}")
    hook = asyncio.run(guard({"tool_name": "Read", "tool_input": {"file_path": "/workspace/.env"}}, "tu_1", None))
    print(f"   as a hook: {json.dumps(hook)[:110]}...")

    print("\n5. BACKSTOP: the SDK's Bash sandbox, if Bash is ever enabled (ClaudeAgentOptions(sandbox=...))")
    print("   " + json.dumps(sdk_sandbox_settings(p)))


if __name__ == "__main__":
    main()
