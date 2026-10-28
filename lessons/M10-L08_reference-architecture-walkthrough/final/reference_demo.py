"""
M10-L08: the reference architecture, end to end. Requirements pick the path, pre-flight checks the deployment
manifest, the compose reference is checked statically, and the evidence pack for the production fleet closes the
four gaps every earlier trace showed.

    uv run python lessons/M10-L08_reference-architecture-walkthrough/final/reference_demo.py
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import yaml

from sentinel.deploy import check_reference, load_deployment, preflight, shortlist
from sentinel.deploy.deployment import PROD_FLEET
from sentinel.evidence import apply_reviews, build_pack, load_map, load_session, score, trace
from sentinel.evidence.review import REVIEW_PATH
from sentinel.monitoring.fleet import load_fleet

REPO = Path(__file__).resolve().parents[3]
REFERENCE = REPO / "deploy" / "reference"


def main() -> None:
    dep, fleet = load_deployment(), load_fleet(PROD_FLEET)
    print("1. REQUIREMENTS -> PATH: each agent's declared requirements against the path catalog")
    for name, d in dep.agents.items():
        ok = [f.path for f in shortlist(d.requirements) if f.ok]
        need = ", ".join(k for k, v in d.requirements.model_dump().items() if v not in (False, "none", 0)) or "none"
        print(f"   {name:17} needs [{need}]\n   {'':17} chose {d.path:22} {'(on the shortlist)' if d.path in ok else '(NOT on the shortlist)'}")

    print(f"\n2. PRE-FLIGHT: {fleet.name}@{fleet.version} against deployment@{dep.version}")
    for name, findings in preflight(fleet, dep).items():
        print(f"   {name:17} {'READY' if not findings else findings}")

    print("\n3. THE REFERENCE ARCHITECTURE (deploy/reference) for aml-triage")
    print(f"   as shipped: {check_reference(REFERENCE, 'aml-triage') or 'PASS'}")
    broken = Path(tempfile.mkdtemp()) / "reference"
    shutil.copytree(REFERENCE, broken)
    doc = yaml.safe_load((broken / "compose.yaml").read_text())
    agent = doc["services"]["agent"]
    agent["ports"] = ["8080:8080"]
    agent["networks"] = ["agent-internal", "egress"]
    agent["environment"]["AWS_SECRET_ACCESS_KEY"] = "copied-from-a-laptop"
    (broken / "compose.yaml").write_text(yaml.safe_dump(doc))
    print("   after a 'quick fix' to get it working:")
    for finding in check_reference(broken, "aml-triage"):
        print(f"     {finding}")

    print("\n4. EVIDENCE: build the pack for the production fleet, then apply the production review")
    out = Path(tempfile.mkdtemp()) / "evidence-pack"
    summary = build_pack(out, fleet=fleet)
    print(f"   proposed {summary['score']}/40, {summary['rating']}; suite passed {summary['suite_passed']}; "
          f"red team {summary['redteam']}; {summary['files']} files signed")
    import json
    results = json.loads((out / "compliance-results.json").read_text())
    card = score(results)
    session = load_session(REVIEW_PATH.with_name("fleet-2026-q4-prod.yaml"))
    confirmed = apply_reviews(card, session)
    print(f"   confirmed {confirmed.score}/40, {confirmed.rating}  (7.5 is still challenged: the banking clock)")
    rows = trace(load_map(), confirmed, results, agent="pa-reviewer")
    print("   pa-reviewer's HIPAA rows after Module 10:")
    for r in rows:
        if r.mapping.regime == "HIPAA":
            print(f"     {r.mapping.id:28} {r.how}")


if __name__ == "__main__":
    main()
