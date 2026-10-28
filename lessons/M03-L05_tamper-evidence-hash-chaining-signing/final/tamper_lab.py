"""
M03-L05: four ways to tamper with an audit log, and which defence catches each.

    uv run python lessons/M03-L05_tamper-evidence-hash-chaining-signing/final/tamper_lab.py

1. Edit a field                      -> the event's own hash no longer matches
2. Edit a field AND recompute hash   -> the NEXT event's prev_hash no longer matches
3. Rewrite the whole chain           -> only the signed checkpoint catches it (needs the key)
4. Delete the last events            -> only the signed checkpoint catches it (needs the key)
"""
from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

from sentinel.audit import GENESIS, AuditHooks, AuditStore, canonical, record_hash, verify_log
from sentinel.audit.simulate import DEMO_AGENT, fixed_clock, simulate_ledger_review

KEY = b"course-demo-key"        # demo only: a real key lives in a secrets manager / KMS


async def build(folder: Path) -> Path:
    clock = fixed_clock()
    store = AuditStore(folder / "audit.jsonl", hmac_key=KEY, checkpoint_every=10, clock=clock)
    hooks = AuditHooks(store, agent=DEMO_AGENT, on_behalf_of="j.chen", clock=clock)
    await simulate_ledger_review(hooks, entries=["JE-1001", "JE-1003", "JE-1010"])
    return store.path


def records(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def save(path: Path, recs: list[dict]) -> None:
    path.write_bytes(b"".join(canonical(r) + b"\n" for r in recs))


def find_decision(recs: list[dict], entry_id: str) -> int:
    return next(i for i, r in enumerate(recs) if r["event_type"] == "decision.recorded" and r["detail"]["entry_id"] == entry_id)


def attack_edit(path: Path) -> None:
    recs = records(path)
    recs[find_decision(recs, "JE-1003")]["detail"]["recommendation"] = "approve"     # escalate -> approve
    save(path, recs)


def attack_edit_and_rehash(path: Path) -> None:
    recs = records(path)
    i = find_decision(recs, "JE-1003")
    recs[i]["detail"]["recommendation"] = "approve"
    recs[i]["hash"] = record_hash(recs[i])
    save(path, recs)


def attack_rewrite_chain(path: Path) -> None:
    recs = records(path)
    recs[find_decision(recs, "JE-1003")]["detail"]["recommendation"] = "approve"
    prev = GENESIS
    for r in recs:                                   # recompute every link: the chain is self-consistent again
        r["prev_hash"] = prev
        r["hash"] = record_hash(r)
        prev = r["hash"]
    save(path, recs)


def attack_truncate(path: Path) -> None:
    save(path, records(path)[:-4])                   # drop the denial and the run result


def main() -> None:
    work = Path(tempfile.mkdtemp())
    original = asyncio.run(build(work / "original"))
    print(verify_log(original, KEY).render(), "\n")
    print(f"{'Attack':<28} {'Without key':<14} {'With key':<10} First problem reported")
    for name, attack in [("1. edit a field", attack_edit), ("2. edit + rehash", attack_edit_and_rehash),
                         ("3. rewrite whole chain", attack_rewrite_chain), ("4. delete the tail", attack_truncate)]:
        folder = work / name.split(".")[0]
        shutil.copytree(original.parent, folder)
        attack(folder / "audit.jsonl")
        no_key = verify_log(folder / "audit.jsonl")
        with_key = verify_log(folder / "audit.jsonl", KEY)
        chain_only = [p for p in no_key.problems if "no key was supplied" not in p]
        first = with_key.problems[0] if with_key.problems else "-"
        print(f"{name:<28} {'CAUGHT' if chain_only else 'missed':<14} {'CAUGHT' if not with_key.ok else 'missed':<10} {first[:70]}")


if __name__ == "__main__":
    main()
