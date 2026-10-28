"""
M07-L04: context isolation. The same change-board job in three configurations, then: where did the CUI go?

Each FALCON ECR carries a canary string (CANARY-CUI-...). If a canary turns up somewhere, controlled
technical data reached that place.

    uv run python lessons/M07-L04_context-isolation-what-crosses-a/final/isolation_demo.py
"""
from __future__ import annotations

import tempfile

from sentinel.boundaries.simulate import SCENARIOS, run_scenario


def main() -> None:
    for kind, what in SCENARIOS.items():
        o = run_scenario(kind, tempfile.mkdtemp())
        print(f"\n{kind.upper()}: {what}")
        print(o.log.table())
        print("  Where the canaries ended up:")
        for place, found in o.leaks().items():
            verdict = ("held" if place == "enclave audit log" else "LEAK") if found else "clean"
            print(f"    {place:22} {verdict:6} {', '.join(found) or '-'}")
        if o.guard and o.guard.handoffs:
            h = o.guard.handoffs[-1]
            print(f"  Handoff contract: ok={h['ok']}  stripped={h['stripped']}")
    print("\nThe subagent's own context was isolated in both multi-agent runs. What leaked was its final message,"
          "\nand the log that recorded it. Those are the channels the contract and the routed log close.")


if __name__ == "__main__":
    main()
