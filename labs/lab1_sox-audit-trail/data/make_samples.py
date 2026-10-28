"""
Regenerate the Lab 1 sample logs (you don't need to; they're committed).

    uv run python labs/lab1_sox-audit-trail/data/make_samples.py

sample_run/   a clean, verified LedgerBot review (signed with the demo key "course-demo-key"),
              plus recommendations.jsonl, the downstream system's own record of each decision
suspicious/   the same review after an insider changed one decision in audit.jsonl and rebuilt the
              hash chain (recommendations.jsonl was not touched)
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from sentinel.audit import GENESIS, AuditHooks, AuditStore, canonical, record_hash
from sentinel.audit.simulate import DECISIONS, DEMO_AGENT, fixed_clock, simulate_ledger_review

HERE = Path(__file__).resolve().parent
KEY = b"course-demo-key"


async def clean_run(folder: Path) -> Path:
    shutil.rmtree(folder, ignore_errors=True)
    clock = fixed_clock()                                      # one clock for events and checkpoints
    store = AuditStore(folder / "audit.jsonl", hmac_key=KEY, checkpoint_every=25, clock=clock)
    hooks = AuditHooks(store, agent=DEMO_AGENT,
                       on_behalf_of="j.chen", correlation_id="run-20261001T140000Z-4be1c0de", clock=clock)
    await simulate_ledger_review(hooks)
    # The downstream system's own copy of each recommendation, stamped with the same correlation ID
    rows = [{"entry_id": e, "recommendation": r, "approver_required": a, "rationale": why, "policy_rule": rule,
             "correlation_id": hooks.correlation_id} for e, (r, a, why, rule) in DECISIONS.items()]
    (folder / "recommendations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return store.path


def make_suspicious(clean: Path, folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(clean.parent, folder)
    path = folder / "audit.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]
    for r in recs:
        if r["event_type"] == "decision.recorded" and r["detail"]["entry_id"] == "JE-1006":
            r["detail"]["recommendation"] = "approve"          # the insider's edit
            r["detail"]["approver_required"] = "none"
    prev = GENESIS
    for r in recs:                                             # ...and a rebuilt chain to hide it
        r["prev_hash"], r["hash"] = prev, None
        r["hash"] = record_hash(r)
        prev = r["hash"]
    path.write_bytes(b"".join(canonical(r) + b"\n" for r in recs))


if __name__ == "__main__":
    clean = asyncio.run(clean_run(HERE / "sample_run"))
    make_suspicious(clean, HERE / "suspicious")
    print("wrote", clean, "and", HERE / "suspicious" / "audit.jsonl")
