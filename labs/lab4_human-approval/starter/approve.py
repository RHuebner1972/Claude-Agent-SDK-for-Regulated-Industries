"""
Lab 4: the reviewer's console. List what's waiting for your role, read the evidence, and sign.

    uv run python approve.py --as m.chen                       # list requests you may decide
    uv run python approve.py --as m.chen APR-000001 approve --reason "Payroll pattern confirmed against 2025 history."

In production --as comes from single sign-on with MFA, never from a command-line flag. This console is a
stand-in so you can play every role in the lab.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from approval_desk.aml_tools import staff_signer
from approval_desk.sod import SegregationOfDutiesError
from aml_pipeline import build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as", dest="user", required=True)
    ap.add_argument("request_id", nargs="?")
    ap.add_argument("meaning", nargs="?", choices=["approve", "reject"])
    ap.add_argument("--reason", default="")
    a = ap.parse_args()
    signer = staff_signer(a.user)
    queue = build_pipeline(WORKSPACE).queue
    if not a.request_id:
        for r in queue.pending(signer.role):
            print(f"\n{r.request_id}  {r.tool}  requested by {r.requested_by}  due {r.due_at:%Y-%m-%d %H:%M} UTC")
            print(f"  Agent's rationale: {r.rationale}")
            print(f"  Evidence: {json.dumps(r.evidence, indent=None)[:400]}")
            print(f"  Your signature will mean: \"{r.meaning_text}\"")
        return
    try:
        r = queue.sign(a.request_id, signer, a.meaning, a.reason)
        print(f"{r.request_id}: signed '{a.meaning}' as {signer.name} ({signer.role}); status {r.status}")
    except SegregationOfDutiesError as exc:
        print("REFUSED:\n  " + "\n  ".join(exc.violations))


if __name__ == "__main__":
    main()
