"""
M08-L03: the red-team corpus against the fleet as deployed, then against a fleet where two controls were
"temporarily" switched off. Every case assumes the model was fooled; it passes only if the control held.

    uv run python lessons/M08-L03_red-teaming-injection-exfiltration-and/final/redteam_demo.py
"""
from __future__ import annotations

from sentinel.monitoring.fleet import load_fleet
from sentinel.monitoring.redteam import load_corpus, run_redteam


def main() -> None:
    cases, version = load_corpus()
    print(f"CORPUS {version}: {len(cases)} cases")
    for c in cases:
        print(f"  {c.id:11} {c.category:15} {c.agent:17} {c.probe:14} {c.technique[:58]}")

    fleet = load_fleet()
    report = run_redteam(fleet)
    print(f"\nAS DEPLOYED: {report.defended}/{len(report.results)} defended {report.by_category()}")
    print(report.table())

    weakened = fleet.model_copy(update={"agents": [
        a.model_copy(update={"controls": {**a.controls, "log_masking": None}}) if a.name == "pa-reviewer" else
        a.model_copy(update={"controls": {**a.controls, "handoff_contracts": False}}) if a.name == "ccb-assistant" else a
        for a in fleet.agents]})
    report = run_redteam(weakened)
    print(f"\nWEAKENED (no log masking; no handoff contract): {report.defended}/{len(report.results)} defended")
    for r in report.results:
        if not r.defended:
            print(f"  BREACHED  {r.id:11} {r.agent:17} {r.observed[:70]}")


if __name__ == "__main__":
    main()
