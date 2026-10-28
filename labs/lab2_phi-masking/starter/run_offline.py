"""
Lab 2, offline: run the scripted prior-auth review through YOUR pipeline, then prove it leaked nothing.

    cd labs/lab2_phi-masking/solution        (or starter/ while you build)
    uv run python run_offline.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from course_data import patients
from sentinel.audit import verify_log

from phi_guard.leakscan import canaries_from, scan_paths
from phi_guard.pa_tools import simulate_pa_review
from phi_guard.vault import ReidentificationDenied
from pipeline import build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"


async def main() -> None:
    for old in WORKSPACE.glob("*.json*"):
        old.unlink()                                              # fresh run each time
    p = build_pipeline(WORKSPACE)
    seen = await simulate_pa_review(p.hooks, p.tools)
    (WORKSPACE / "model_context.json").write_text(json.dumps(seen, indent=1), encoding="utf-8")
    (WORKSPACE / "recommendations.json").write_text(json.dumps(p.recorded, indent=1), encoding="utf-8")

    key = os.getenv("AUDIT_HMAC_KEY", "course-demo-key").encode()
    print(verify_log(p.store.path, key).render().splitlines()[0])

    rec = p.recorded[0]
    print(f"\nReviewer queue stores: {rec['request_id']} {rec['recommendation']}: {rec['rationale']}")
    for who, role, purpose in [("k.osei", "care_manager", "treatment"), ("d.ruiz", "data_analyst", "analytics")]:
        try:
            text = p.vault.reidentify_text(rec["rationale"], requester=who, role=role, purpose=purpose)
            print(f"  {who} ({role}) sees: {text}")
        except ReidentificationDenied as exc:
            print(f"  {who} ({role}) DENIED: {exc}")

    files = ["audit.jsonl", "vault_audit.jsonl", "vault.json", "model_context.json", "recommendations.json"]
    report = scan_paths([WORKSPACE / f for f in files], canaries_from(patients()), use_detector=False)
    print("\nLeak scan (every identifier of all 8 synthetic patients):\n" + report.render())


if __name__ == "__main__":
    asyncio.run(main())
