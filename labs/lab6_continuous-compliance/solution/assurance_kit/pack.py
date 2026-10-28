"""Build and verify the evidence pack (rubric 7.6): one command, one folder, every file hashed and the index signed.

    python assure.py                                                # build (runs suite, red team, fleet)
    verify_pack("out/evidence-pack")                                # detects any edited, added or missing file
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sentinel.audit import verify_log
from .alerts import evaluate
from .change import check_change_control, load_changes
from .dashboard import write_dashboard
from .fleet import Fleet, load_fleet
from .metrics import FleetMetrics
from .redteam import run_redteam
from .runs import KEY, run_fleet

from .rubric import ATTESTATIONS_PATH, load_rubric, score

SUITE = Path(os.getenv("COMPLIANCE_SUITE") or Path(__file__).resolve().parents[1] / "compliance")
MANIFEST, SIGNATURE = "manifest.json", "manifest.sig"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write(out: Path, name: str, payload: Any) -> Path:
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload, indent=1, default=str),
                    encoding="utf-8")
    return path


def run_suite(results_path: Path, suite: Path = SUITE, env: dict | None = None) -> dict:
    """Run the compliance suite in a subprocess (exactly as CI does) and load its results file."""
    subprocess.run([sys.executable, "-m", "pytest", str(suite), "-q", "-p", "no:cacheprovider",
                    f"--compliance-results={results_path}"], env={**os.environ, **(env or {})},
                   capture_output=True, text=True)
    return json.loads(results_path.read_text(encoding="utf-8"))


def crosswalk(rubric: dict, card) -> str:
    regs = rubric["pillar_regulations"]
    lines = ["# Control crosswalk: rubric item → status → regulatory anchors", "",
             "Anchors are each pillar's references from the course's Regulatory Mapping Framework. Confirm the "
             "applicable ones with your compliance partner; not every regime applies to every agent.", ""]
    for pillar in sorted(regs):
        lines += [f"## {pillar}", "", "| Item | Status | Criterion |", "|---|---|---|"]
        lines += [f"| {i.id}{' ★' if i.critical else ''} | {i.status} | {i.criterion} |"
                  for i in card.items if i.pillar == pillar]
        lines += ["", "| Regime | Anchors |", "|---|---|"] + [f"| {k} | {v} |" for k, v in regs[pillar].items()] + [""]
    return "\n".join(lines)


def scorecard_md(card, fleet: Fleet, generated: str, commit: str) -> str:
    lines = [f"# Evidence pack: {fleet.name}", "",
             f"**Proposed rating: {card.rating}**, {card.score}/40, critical items {'all met' if card.critical_met else 'NOT all met'}",
             f"Generated {generated} · commit {commit} · fleet manifest {fleet.name}@{fleet.version}", "",
             "This score is proposed by automation. A reviewer who is not the author confirms each item before it is "
             "relied on (rubric scoring rule).", "", "| Pillar | Points |", "|---|---|"]
    lines += [f"| {p} | {a}/{b} |" for p, (a, b) in card.by_pillar().items()]
    lines += ["", "| Item | Status | Evidence |", "|---|---|---|"]
    lines += [f"| {i.id}{' ★' if i.critical else ''} | {i.status} | {'<br>'.join(i.evidence[:4])}"
              f"{' …' if len(i.evidence) > 4 else ''} |" for i in card.items]
    return "\n".join(lines) + "\n"


def sign_manifest(out: Path, key: bytes) -> dict:
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name not in (MANIFEST, SIGNATURE))
    manifest = {"schema": "sentinel.evidence-manifest/1", "generated": datetime.now(timezone.utc).isoformat(),
                "files": {str(p.relative_to(out)).replace(os.sep, "/"): _sha256(p) for p in files}}
    body = json.dumps(manifest, indent=1, sort_keys=True)
    (out / MANIFEST).write_text(body, encoding="utf-8")
    (out / SIGNATURE).write_text(hmac.new(key, body.encode(), hashlib.sha256).hexdigest(), encoding="utf-8")
    return manifest


def verify_pack(out: str | Path, key: bytes = KEY) -> list[str]:
    out, problems = Path(out), []
    body = (out / MANIFEST).read_text(encoding="utf-8")
    if not hmac.compare_digest(hmac.new(key, body.encode(), hashlib.sha256).hexdigest(),
                               (out / SIGNATURE).read_text(encoding="utf-8").strip()):
        problems.append("manifest signature does not verify: the index itself was changed or the key is wrong")
    listed = json.loads(body)["files"]
    for name, digest in listed.items():
        path = out / name
        if not path.exists():
            problems.append(f"missing: {name}")
        elif _sha256(path) != digest:
            problems.append(f"modified: {name}")
    present = {str(p.relative_to(out)).replace(os.sep, "/") for p in out.rglob("*")
               if p.is_file() and p.name not in (MANIFEST, SIGNATURE)}
    problems += [f"added after signing: {n}" for n in sorted(present - set(listed))]
    return problems


def build_pack(out: str | Path, *, results: dict | None = None, redteam: dict | None = None,
               fleet: Fleet | None = None, suite: Path = SUITE, key: bytes = KEY,
               attestations_path: Path = ATTESTATIONS_PATH) -> dict[str, Any]:
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    fleet = fleet or load_fleet()
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = results or run_suite(out / "compliance-results.json", suite)
    _write(out, "compliance-results.json", results)
    redteam = redteam or run_redteam(fleet).to_dict()
    _write(out, "redteam-report.json", redteam)

    runs = run_fleet(fleet, out / "runs")
    metrics = FleetMetrics()
    verification = {}
    for name, run in runs.items():
        metrics.ingest(run, key)
        verification[name] = {which: (lambda r: {"ok": r.ok, "events": r.events, "checkpoints": r.checkpoints_checked,
                                                 "problems": r.problems})(verify_log(p, key))
                               for which, p in run.logs.items()}
    snapshot = metrics.snapshot()
    alerts = evaluate(snapshot, metrics=metrics)
    changes = check_change_control(fleet, load_changes())
    _write(out, "metrics.json", snapshot)
    _write(out, "alerts.json", [a.to_dict() for a in alerts])
    _write(out, "audit-verification.json", verification)
    _write(out, "change-control.json", {"fingerprints": fleet.fingerprints(), "findings": changes})
    write_dashboard(out / "dashboard.html", snapshot, alerts, agents=[a.name for a in fleet.agents], metrics=metrics,
                    suite=results, redteam=redteam, changes=changes)

    for name in (fleet.path, attestations_path):
        shutil.copy(name, out / Path(name).name)
    for agent in fleet.agents:
        for cfg in agent.config_paths():
            dest = out / "configs" / agent.name / cfg.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cfg, dest)

    rubric = load_rubric()
    card = score(results, rubric=rubric)
    _write(out, "scorecard.json", card.to_dict())
    _write(out, "scorecard.md", scorecard_md(card, fleet, generated, results.get("commit", "local")))
    _write(out, "control-crosswalk.md", crosswalk(rubric, card))
    manifest = sign_manifest(out, key)
    return {"out": str(out), "score": card.score, "rating": card.rating, "critical_met": card.critical_met,
            "suite_passed": results.get("exit_status") == 0, "redteam": f"{redteam['defended']}/{redteam['cases']}",
            "alerts": len(alerts), "files": len(manifest["files"])}
