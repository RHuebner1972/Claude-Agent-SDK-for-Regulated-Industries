"""
Lab 5, offline: the change-board job, unguarded and then gated, plus where the CUI canaries ended up.

    cd labs/lab5_data-boundaries/solution        (or starter/ while you build)
    uv run python run_offline.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sentinel.audit import verify_log

from boundary_kit.simulate import GATED, ISOLATION, run_scenario, run_script
from boundary_pipeline import build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace" / "offline"


def where(p, seen: list[str]) -> None:
    canaries = p.store.canaries()
    places = {"orchestrator context": "\n".join(seen), "general audit log": p.general_log.read_text(),
              "enclave audit log": p.enclave_log.read_text()}
    for place, text in places.items():
        found = [c for c in canaries if c in text]
        verdict = ("held" if place == "enclave audit log" else "LEAK") if found else "clean"
        print(f"  {place:22} {verdict:6} {', '.join(found) or '-'}")


def baseline() -> None:
    print("BASELINE: one agent with every tool (no boundaries)")
    base = run_scenario("naive", WORKSPACE / "baseline")
    print(base.log.table())
    for place, found in base.leaks().items():
        if place != "enclave audit log":
            print(f"  {place:22} {'LEAK' if found else 'clean':6} {', '.join(found) or '-'}")


async def gated() -> None:
    p = build_pipeline(WORKSPACE)
    print("\nRESIDENCY (agent cards vs. deployment)")
    for name, findings in p.residency.items():
        print(f"  {name:24} {'; '.join(findings) or 'OK'}")

    print("\nGATED RUN 1: the change-board job with a cleared subagent")
    log = await run_script(p.tools, ISOLATION, audit=p.audit, guard=p.guard)
    print(log.table())
    seen = list(log.seen)

    print("\nGATED RUN 2: boundary tests (orchestrator reaching for CUI, cross-program, leaky handoff, rogue delegate)")
    log2 = await run_script(p.tools, GATED, audit=p.audit, guard=p.guard, session_id="sess-ccb-8d02")
    print(log2.table())
    seen += log2.seen

    print("\nHANDOFFS")
    for h in p.guard.handoffs:
        print(f"  {h['subagent']:24} ok={h['ok']!s:5} stripped={h['stripped'] or '-'} findings={h['findings'] or '-'}")
    print("\nWHERE THE CUI CANARIES ENDED UP")
    where(p, seen)

    key = os.getenv("AUDIT_HMAC_KEY", "course-demo-key").encode()
    for path in (p.general_log, p.enclave_log):
        print("  " + verify_log(path, key).render().splitlines()[0])


if __name__ == "__main__":
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for old in list(WORKSPACE.rglob("*.jsonl")):
        old.unlink()                                                  # fresh run each time
    baseline()
    asyncio.run(gated())
