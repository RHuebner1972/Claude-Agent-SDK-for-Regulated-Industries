"""
M08-L07: build the evidence pack in one call, verify it, then show what happens when someone "tidies up" a file.

    uv run python lessons/M08-L07_automated-evidence-packs/final/evidence_demo.py
    # or exactly what CI runs:  uv run python -m sentinel.evidence build --out out/evidence-pack
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from sentinel.evidence import build_pack, verify_pack


def main() -> None:
    out = Path(tempfile.mkdtemp()) / "evidence-pack"
    summary = build_pack(out)
    print(json.dumps(summary, indent=1))
    print("\nFILES")
    for p in sorted(out.iterdir()):
        print(f"  {p.name}{'/' if p.is_dir() else ''}")
    print("\nSCORECARD (first lines)")
    print("\n".join((out / "scorecard.md").read_text(encoding="utf-8").splitlines()[:16]))
    card = json.loads((out / "scorecard.json").read_text(encoding="utf-8"))
    print("\nNot yet evidenced:", [(i["id"], i["evidence"][0]) for i in card["items"] if not i["points"]])

    print("\nVERIFY:", verify_pack(out) or "VERIFIED")
    md = out / "scorecard.md"
    md.write_text(md.read_text(encoding="utf-8").replace("missing", "met (attested)"), encoding="utf-8")
    print("After someone edits scorecard.md:", verify_pack(out))


if __name__ == "__main__":
    main()
