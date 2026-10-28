"""Lab 6 solution: assurance_kit (sentinel.monitoring + the evidence pack, as one package).
P7 Continuous Assurance (Module 8, Lab 6): the fleet manifest, offline fleet runs, a pytest plugin that turns
tests into control evidence, a red-team runner, OpenTelemetry metrics, alert rules, a dashboard, change control
and incident notification clocks.

    fleet = load_fleet()                     # policies/fleet.yaml, or FLEET_FILE
    runs  = run_fleet(fleet, workdir)        # every agent, offline, as the manifest configures it
    pytest compliance                        # with assurance_kit.pytest_plugin -> compliance-results.json
"""
from .alerts import Alert, AlertRule, evaluate, load_rules
from .change import ChangeLog, ChangeRecord, check_change_control, load_changes
from .dashboard import render_dashboard, write_dashboard
from .fleet import Fleet, FleetAgent, load_fleet
from .incident import Deadline, notification_clocks
from .metrics import FleetMetrics, total
from .runs import FleetRun, run_agent, run_fleet

__all__ = ["Alert", "AlertRule", "ChangeLog", "ChangeRecord", "Deadline", "Fleet", "FleetAgent", "FleetMetrics",
           "FleetRun", "check_change_control", "evaluate", "load_changes", "load_fleet", "load_rules",
           "notification_clocks", "render_dashboard", "run_agent", "run_fleet", "total", "write_dashboard"]
