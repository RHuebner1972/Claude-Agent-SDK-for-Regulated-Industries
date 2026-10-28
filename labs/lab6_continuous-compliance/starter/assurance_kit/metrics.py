"""Runtime metrics for the fleet with OpenTelemetry (rubric 7.3), derived from the audit trail.

The audit log is already the record of every call, denial, approval and handoff, so the metrics come from it:
one source of truth, and a metric can always be traced back to the events behind it.

    m = FleetMetrics()                       # in-memory reader for tests and the dashboard
    m.ingest(run)                            # a FleetRun (or any audit log + agent name)
    snap = m.snapshot()                      # {"agent.policy.denials": [{"attributes": {...}, "value": 3}], ...}

In production, add an exporter instead of (or alongside) the in-memory reader:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    FleetMetrics(readers=[PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=...))])
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader, MetricReader
from opentelemetry.sdk.resources import Resource

from sentinel.audit import verify_log

PII_TOKEN = re.compile(r"\[\[([A-Z_]+?)_[0-9a-f]{8}\]\]")


def _short(tool: str | None) -> str:
    return (tool or "?").rsplit("__", 1)[-1]


def _rule(authority: str | None) -> str:
    """'INJ-003 (complaint-handling@1.0.0 ...)' -> INJ-003; 'APR-000003 expired' -> APPROVAL-EXPIRED."""
    if not authority:
        return "permission-rule"
    head, *rest = authority.split()
    if head.startswith("APR-"):
        return "APPROVAL-" + (rest[0].upper() if rest else "PENDING")
    return head.strip("[]")


def _ts(event: dict) -> datetime:
    return datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))


class FleetMetrics:
    def __init__(self, readers: Iterable[MetricReader] | None = None, service: str = "sentinel-fleet"):
        self.reader = InMemoryMetricReader()
        self.provider = MeterProvider(metric_readers=[self.reader, *(readers or [])],
                                      resource=Resource.create({"service.name": service}))
        meter = self.provider.get_meter("sentinel.monitoring", "1.0.0")
        self.tool_calls = meter.create_counter("agent.tool.calls", description="Tool calls by outcome")
        self.denials = meter.create_counter("agent.policy.denials", description="Denied tool calls by rule")
        self.pii_masked = meter.create_counter("agent.pii.masked", description="Identifiers masked before logging")
        self.leaks = meter.create_counter("agent.restricted_data.leaks",
                                          description="Canary values found where they must never be")
        self.approval_latency = meter.create_histogram("agent.approval.latency", unit="s",
                                                       description="Request to final decision")
        self.approvals = meter.create_counter("agent.approvals", description="Approval outcomes")
        self.handoffs = meter.create_counter("agent.boundary.handoffs", description="Subagent handoffs by result")
        self.cost = meter.create_counter("agent.cost.usd", unit="USD", description="Model cost per run")
        self.runs = meter.create_counter("agent.runs", description="Completed runs")
        self.errors = meter.create_counter("agent.errors", description="Tool failures and failed runs")
        self.audit_checks = meter.create_counter("assurance.audit.verifications", description="Audit-log verifications")
        self.latencies: dict[str, list[float]] = defaultdict(list)    # raw values, for exact percentiles

    # ---------------------------------------------------------------------------------------------- ingest
    def ingest_events(self, agent: str, events: list[dict], canaries: Iterable[str] = ()) -> None:
        # TODO 5: audit events -> OpenTelemetry instruments. a = {"agent": agent}. For each event e:
        # tool.completed  tool_calls.add(1, {**a, "tool": _short(...), "outcome": "allowed"})
        # tool.denied     tool_calls (outcome "denied") AND denials.add(1, {**a, "rule": _rule(e["authority"])})
        # tool.failed     errors.add(1, {**a, "kind": "tool"})
        # approval.requested   remember requested[e["detail"]["request_id"]] = _ts(e)
        # approval.decided     n, m = detail["approvals"].split("/"); status = "rejected" if e["outcome"] == "denied"
        #                      else "approved" if n == m else "partial". Skip partial. Otherwise approvals.add(1, status)
        #                      and, if requested, record latency seconds in approval_latency AND self.latencies[agent]
        # approval.escalated   approvals.add(1, {**a, "status": detail["status"]})
        # decision.recorded by actor id "boundary-guard"   handoffs.add(1, result "accepted"/"rejected" from e["reason"])
        # run.completed   runs.add(1, a); cost.add(detail total_cost_usd or 0, a); outcome not success -> errors (kind "run")
        # Then for EVERY event: text = json.dumps(e); each PII_TOKEN match -> pii_masked.add(1, entity);
        # each canary found in text -> leaks.add(1, {**a, "event_type": et}).
        raise NotImplementedError("Lab 6: ingest_events")

    def ingest_log(self, agent: str, path: str | Path, canaries: Iterable[str] = (), key: bytes | None = None) -> None:
        path = Path(path)
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.ingest_events(agent, events, canaries)
        if key is not None:
            report = verify_log(path, key)
            ok = report.ok and report.checkpoints_checked > 0
            self.audit_checks.add(1, {"agent": agent, "log": path.parent.name if path.parent.name == "enclave"
                                      else "general", "result": "verified" if ok else "failed"})

    def ingest(self, run, key: bytes | None = None) -> None:
        """A FleetRun: the general log is checked for leaks; an enclave log is expected to hold restricted data."""
        self.ingest_log(run.agent.name, run.logs["general"], run.canaries, key)
        if run.logs.get("enclave"):
            self.ingest_log(run.agent.name, run.logs["enclave"], (), key)
        if run.seen:
            for c in run.canaries:
                if c and c in run.seen:
                    self.leaks.add(1, {"agent": run.agent.name, "event_type": "model_context"})

    # -------------------------------------------------------------------------------------------- read out
    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        data = self.reader.get_metrics_data()
        for rm in (data.resource_metrics if data else []):
            for sm in rm.scope_metrics:
                for metric in sm.metrics:
                    points = []
                    for p in metric.data.data_points:
                        if hasattr(p, "bucket_counts"):
                            points.append({"attributes": dict(p.attributes), "count": p.count, "sum": p.sum,
                                           "max": p.max, "value": p.sum})
                        else:
                            points.append({"attributes": dict(p.attributes), "value": p.value})
                    out[metric.name] = points
        return out

    def p95_latency(self, agent: str) -> float | None:
        xs = sorted(self.latencies.get(agent, []))
        return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))] if xs else None


def total(snapshot: dict, name: str, **attrs: Any) -> float:
    """Sum a metric's points whose attributes match, e.g. total(snap, "agent.policy.denials", agent="aml-triage")."""
    return sum(p["value"] for p in snapshot.get(name, [])
               if all(p["attributes"].get(k) == v for k, v in attrs.items()))
