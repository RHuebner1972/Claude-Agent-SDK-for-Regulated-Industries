"""A one-file HTML dashboard for the fleet: suite status, red team, alerts and per-agent metrics (rubric 7.3).

Static on purpose: it's also an evidence artifact, so it must render the same in a year with no server behind it.
In production the same metrics go to your observability stack through an OTLP exporter.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .metrics import total

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#0f1b2d;--muted:#5c6b7a;--line:#e3e7ec;--ok:#2a9d8f;--warn:#f2a541;--bad:#e4572e;--bar:#457b9d}
@media (prefers-color-scheme:dark){:root{--bg:#0f1b2d;--card:#16243a;--ink:#eef2f6;--muted:#a8b3c0;--line:#2a3b55;--bar:#a8dadc}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 40px}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}
.sub{color:var(--muted)}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.tile b{display:block;font-size:24px}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{font-size:12px;color:var(--muted);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}.wrap{overflow-x:auto}.pill{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;font-weight:600;color:#fff}
.page{background:var(--bad)}.ticket{background:var(--warn);color:#0f1b2d}.info{background:var(--muted)}
svg{vertical-align:middle}
"""


def _bar(fraction: float, width: int = 80) -> str:
    w = max(0, min(1, fraction)) * width
    return (f'<svg width="{width}" height="8" role="img" aria-label="{fraction:.0%}"><rect width="{width}" height="8" '
            f'rx="4" fill="var(--line)"/><rect width="{w:.1f}" height="8" rx="4" fill="var(--bar)"/></svg>')


def agent_rows(snapshot: dict, agents: list[str], metrics: Any = None) -> list[dict[str, Any]]:
    rows = []
    for a in agents:
        allowed = total(snapshot, "agent.tool.calls", agent=a, outcome="allowed")
        denied = total(snapshot, "agent.tool.calls", agent=a, outcome="denied")
        runs = total(snapshot, "agent.runs", agent=a) or 1
        rules = sorted({p["attributes"]["rule"] for p in snapshot.get("agent.policy.denials", [])
                        if p["attributes"].get("agent") == a})
        p95 = metrics.p95_latency(a) if metrics is not None else None
        rows.append({"agent": a, "calls": int(allowed + denied), "denied": int(denied),
                     "deny_rate": denied / (allowed + denied) if allowed + denied else 0.0, "rules": rules,
                     "pii_masked": int(total(snapshot, "agent.pii.masked", agent=a)),
                     "leaks": int(total(snapshot, "agent.restricted_data.leaks", agent=a)),
                     "approved": int(total(snapshot, "agent.approvals", agent=a, status="approved")),
                     "expired": int(total(snapshot, "agent.approvals", agent=a, status="expired")),
                     "approval_p95_h": round(p95 / 3600, 2) if p95 is not None else None,
                     "handoffs_rejected": int(total(snapshot, "agent.boundary.handoffs", agent=a, result="rejected")),
                     "cost_per_run": round(total(snapshot, "agent.cost.usd", agent=a) / runs, 4),
                     "audit_ok": total(snapshot, "assurance.audit.verifications", agent=a, result="failed") == 0})
    return rows


def render_dashboard(snapshot: dict, alerts: list, *, agents: list[str], metrics: Any = None,
                     suite: dict | None = None, redteam: dict | None = None, changes: dict | None = None,
                     title: str = "Sentinel fleet: compliance dashboard") -> str:
    e = html.escape
    rows = agent_rows(snapshot, agents, metrics)
    suite = suite or {}
    passed = sum(r["outcome"] == "passed" for r in suite.get("results", []))
    ran = len(suite.get("results", []))
    rt_ok = redteam and redteam["defended"] == redteam["cases"]
    pages = sum(a.severity == "page" for a in alerts)
    tiles = [
        ("Compliance suite", f"{passed}/{ran}" if ran else "not run", "ok" if ran and passed == ran else "bad"),
        ("Red team defended", f"{redteam['defended']}/{redteam['cases']}" if redteam else "not run", "ok" if rt_ok else "bad"),
        ("Policy denials", f"{int(total(snapshot, 'agent.policy.denials'))}", ""),
        ("PII masked before logging", f"{int(total(snapshot, 'agent.pii.masked'))}", ""),
        ("Restricted-data leaks", f"{int(total(snapshot, 'agent.restricted_data.leaks'))}",
         "bad" if total(snapshot, "agent.restricted_data.leaks") else "ok"),
        ("Approvals decided / expired", f"{int(total(snapshot, 'agent.approvals', status='approved'))} / "
                                        f"{int(total(snapshot, 'agent.approvals', status='expired'))}", ""),
        ("Open alerts (page)", f"{len(alerts)} ({pages})", "bad" if pages else ("warn" if alerts else "ok")),
    ]
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width,initial-scale=1'><title>Fleet dashboard</title><style>{CSS}</style></head><body><main>",
           f"<h1>{e(title)}</h1><div class='sub'>Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · "
           f"commit {e(str(suite.get('commit', 'local')))} · synthetic data</div><div class='tiles'>"]
    out += [f"<div class='tile'><span class='sub'>{e(k)}</span><b class='{c}'>{e(v)}</b></div>" for k, v, c in tiles]
    out.append("</div><h2>Alerts</h2>")
    if alerts:
        out.append("<div class='wrap'><table><tr><th>Severity</th><th>Rule</th><th>Agent</th><th>Value</th><th>Runbook</th></tr>")
        out += [f"<tr><td><span class='pill {a.severity}'>{a.severity}</span></td><td>{e(a.rule)}<br><span class='sub'>"
                f"{e(a.title)}</span></td><td>{e(a.agent)}</td><td class='n'>{a.value:g} &gt; {a.threshold:g}</td>"
                f"<td>{e(a.runbook)}</td></tr>" for a in alerts]
        out.append("</table></div>")
    else:
        out.append("<p class='ok'>No alerts.</p>")
    out.append("<h2>Agents</h2><div class='wrap'><table><tr><th>Agent</th><th>Tool calls</th><th>Deny rate</th>"
               "<th>Denials by rule</th><th>PII masked</th><th>Leaks</th><th>Approvals (expired)</th>"
               "<th>Approval p95 (h)</th><th>Handoffs rejected</th><th>Cost/run</th><th>Audit log</th><th>Change control</th></tr>")
    for r in rows:
        chg = (changes or {}).get(r["agent"])
        chg_cell = "<span class='ok'>approved</span>" if chg == [] else (
            f"<span class='bad'>{e(chg[0][:7])}</span>" if chg else "<span class='sub'>n/a</span>")
        out.append(f"<tr><td><b>{e(r['agent'])}</b></td><td class='n'>{r['calls']}</td>"
                   f"<td class='n'>{r['deny_rate']:.0%} {_bar(r['deny_rate'])}</td><td>{e(', '.join(r['rules']) or '-')}</td>"
                   f"<td class='n'>{r['pii_masked']}</td><td class='n {'bad' if r['leaks'] else ''}'>{r['leaks']}</td>"
                   f"<td class='n'>{r['approved']} ({r['expired']})</td><td class='n'>{'-' if r['approval_p95_h'] is None else r['approval_p95_h']}</td>"
                   f"<td class='n'>{r['handoffs_rejected']}</td><td class='n'>${r['cost_per_run']:.2f}</td>"
                   f"<td class='{'ok' if r['audit_ok'] else 'bad'}'>{'verified' if r['audit_ok'] else 'FAILED'}</td><td>{chg_cell}</td></tr>")
    out.append("</table></div>")
    if redteam:
        out.append("<h2>Red team</h2><div class='wrap'><table><tr><th>Category</th><th>Cases</th><th>Defended</th></tr>")
        out += [f"<tr><td>{e(c)}</td><td class='n'>{v['cases']}</td><td class='n {'ok' if v['defended'] == v['cases'] else 'bad'}'>"
                f"{v['defended']}</td></tr>" for c, v in redteam["by_category"].items()]
        out.append("</table></div>")
    out.append("<p class='sub'>Metrics are derived from each agent's hash-chained audit log; every number traces back "
               "to the events behind it.</p></main></body></html>")
    return "".join(out)


def write_dashboard(path: str | Path, *args, **kwargs) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(*args, **kwargs), encoding="utf-8")
    return path
