"""
M08-L04: run the fleet, turn each audit log into OpenTelemetry metrics, evaluate the alert rules, and render the
dashboard. Then rerun with a regression and watch the alerts change.

    uv run python lessons/M08-L04_runtime-monitoring-with-opentelemetry/final/monitoring_demo.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sentinel.monitoring import FleetMetrics, evaluate, load_fleet, run_fleet, total, write_dashboard
from sentinel.monitoring.runs import KEY

OUT = Path(__file__).resolve().parent / "out"


def observe(fleet, label: str) -> FleetMetrics:
    metrics = FleetMetrics()
    for run in run_fleet(fleet, tempfile.mkdtemp()).values():
        metrics.ingest(run, KEY)
    snap = metrics.snapshot()
    print(f"\n{label}")
    for name in ("agent.tool.calls", "agent.policy.denials", "agent.pii.masked", "agent.restricted_data.leaks",
                 "agent.approvals", "agent.cost.usd"):
        print(f"  {name:30} {total(snap, name):g}")
    print(f"  {'agent.approval.latency p95':30} {metrics.p95_latency('aml-triage') / 3600:.1f} h (aml-triage)")
    alerts = evaluate(snap, metrics=metrics)
    print("  Alerts:" if alerts else "  Alerts: none")
    for a in alerts:
        print("   ", a.line())
    path = write_dashboard(OUT / f"{label.split(':')[0].lower().replace(' ', '-')}.html", snap, alerts,
                           agents=[a.name for a in fleet.agents], metrics=metrics)
    print(f"  Dashboard: {path}")
    return metrics


def main() -> None:
    fleet = load_fleet()
    observe(fleet, "AS DEPLOYED")
    leaky = fleet.model_copy(update={"agents": [
        a.model_copy(update={"controls": {**a.controls, "handoff_contracts": False}}) if a.name == "ccb-assistant"
        else a for a in fleet.agents]})
    observe(leaky, "REGRESSION: ccb-assistant without its handoff contract")


if __name__ == "__main__":
    main()
