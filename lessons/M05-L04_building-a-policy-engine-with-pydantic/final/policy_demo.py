"""
M05-L04: load a versioned YAML policy into Pydantic models, then evaluate requests and read the decisions.

    uv run python lessons/M05-L04_building-a-policy-engine-with-pydantic/final/policy_demo.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import ValidationError

from sentinel.policy import PolicyEngine, Subject, build_context, load_policy
from sentinel.policy.complaint_tools import COMPLAINTS_POLICY, ComplaintStore


def main() -> None:
    policy, content_hash = load_policy(COMPLAINTS_POLICY)
    engine = PolicyEngine(policy, content_hash)
    print(f"Loaded {engine.version}: {len(policy.rules)} rules, default {policy.default_effect.upper()}")

    store = ComplaintStore()
    qa = Subject(user="r.patel", role="qa_specialist", purpose="complaint_handling", agent="triage-assistant")
    env = {"tainted": False, "injection_suspected": False}
    for tool, args in [("close_complaint", {"complaint_id": "CMP-3001"}),     # not reportable
                       ("close_complaint", {"complaint_id": "CMP-3002"}),     # reportable, MDR not filed
                       ("close_complaint", {"complaint_id": "CMP-3003"}),     # MDR determination pending
                       ("delete_complaint", {"complaint_id": "CMP-3001"})]:   # no rule mentions it
        d = engine.evaluate(build_context(qa, tool, args, store.resolve(tool, args), env))
        print(f"  {d.effect.upper():5} {tool:17} {args['complaint_id']}  {d.rule_id:12} matched={d.matched}")
    print("\nA decision is data. This is what gets logged:")
    print(" ", d.model_dump_json())

    # Bad policy never loads: Pydantic rejects it before it can make a single decision.
    broken = Path(tempfile.mkdtemp()) / "broken.yaml"
    broken.write_text("name: x\nversion: 1.0\nrules:\n  - {id: close-ok, description: anything goes, "
                      "effect: permit, tools: ['*']}\n")
    try:
        load_policy(broken)
    except ValidationError as exc:
        print(f"\nBroken policy rejected with {exc.error_count()} errors:")
        for e in exc.errors():
            print(f"  {'.'.join(map(str, e['loc']))}: {e['msg']}")

    # Change one character and the version changes, so every decision says exactly which policy made it.
    edited = Path(tempfile.mkdtemp()) / "complaints.yaml"
    edited.write_text(COMPLAINTS_POLICY.read_text().replace("value: pending", "value: pendng"))
    print(f"\nOriginal {content_hash}  vs  one-character edit {load_policy(edited)[1]}")


if __name__ == "__main__":
    main()
