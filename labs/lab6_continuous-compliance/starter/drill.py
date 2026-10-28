"""
Lab 6 tabletop drill (rubric 7.5): a regression reaches production at Northshore Health Plan, the leak alert pages,
and you produce the incident record: timeline, containment, and the notification clocks that started.

    uv run python drill.py                       # -> out/tabletop-record.md
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from assurance_kit.alerts import evaluate
from assurance_kit.fleet import load_fleet
from assurance_kit.incident import notification_clocks
from assurance_kit.metrics import FleetMetrics, total
from assurance_kit.runs import KEY, run_fleet
from seed_regression import seed

HERE = Path(__file__).resolve().parent
T0 = datetime(2026, 10, 28, 14, 5, tzinfo=timezone.utc)          # the regression ships


def main() -> None:
    fleet = load_fleet(seed("masking", Path(tempfile.mkdtemp()) / "fleet.yaml"))
    metrics = FleetMetrics()
    for run in run_fleet(fleet, tempfile.mkdtemp()).values():
        metrics.ingest(run, KEY)
    snap = metrics.snapshot()
    pages = [a for a in evaluate(snap, metrics=metrics) if a.severity == "page"]
    leaks = int(total(snap, "agent.restricted_data.leaks", agent="pa-reviewer"))
    detected = T0 + timedelta(minutes=35)                        # first metrics export after the run
    timeline = [
        (T0, "Prompt-template refactor deployed to pa-reviewer WITHOUT a change record (CHG-001 would have blocked it in CI)"),
        (detected, f"ALR-LEAK pages: {leaks} identifier hits in pa-reviewer's general audit log"),
        (detected + timedelta(minutes=12), "On-call contains: kill switch on pa-reviewer; previous manifest restored"),
        (detected + timedelta(minutes=40), "Scope: 8 synthetic members' identifiers in one log; one member is an EU resident"),
        (detected + timedelta(hours=3), "Privacy Officer opens breach risk assessment (45 CFR 164.402); log copy preserved, "
                                        "exposed lines restricted"),
    ]
    clocks = notification_clocks(detected, ["hipaa", "gdpr"], affected=8, max_in_one_state=8)
    lines = ["# Tabletop record: PHI in the prior-auth assistant's audit log", "",
             "Synthetic exercise, Northshore Health Plan (Lab 2's payer). Course material, not legal advice.", "",
             f"**Alerts that paged:** {', '.join(f'{a.rule} ({a.agent})' for a in pages) or 'none'}", "",
             "## Timeline (UTC)", "", "| Time | Event |", "|---|---|"]
    lines += [f"| {t:%Y-%m-%d %H:%M} | {e} |" for t, e in timeline]
    lines += ["", "## Notification clocks (if the risk assessment finds a reportable breach)", "",
              "| Regime | Audience | Due | Clock starts | Citation | Note |", "|---|---|---|---|---|---|"]
    lines += [f"| {d.regime} | {d.audience} | {d.due} | {d.starts} | {d.citation} | {d.note} |" for d in clocks]
    lines += ["", "## Control that failed, and the fix", "",
              "- Failed: change control. The manifest change bypassed CI; the suite (2.2, 2.3) and red team (RT-INJ-003) "
              "would have failed the build.",
              "- Fix: require the compliance check on the deploy branch; add a red-team case for this template pattern.",
              "", "## Sign-off", "", "| Role | Name | Date |", "|---|---|---|",
              "| Incident lead | | |", "| Privacy Officer | | |", "| Agent owner (UM director) | | |"]
    out = HERE / "out" / "tabletop-record.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:20]))
    print(f"\n... written to {out}")


if __name__ == "__main__":
    main()
