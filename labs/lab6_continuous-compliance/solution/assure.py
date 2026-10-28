"""
Lab 6: the whole assurance pipeline in one command: compliance suite, red team, fleet run, metrics, alerts,
dashboard, change control, scorecard, crosswalk, signed manifest.

    cd labs/lab6_continuous-compliance/solution        (or starter/ while you build)
    uv run python assure.py                            # -> out/evidence-pack/ (open dashboard.html)
    uv run python assure.py --fleet out/proposed-fleet.yaml --strict     # CI gate for a proposed change
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the fleet's evidence pack in one command.")
    ap.add_argument("--out", default=str(HERE / "out" / "evidence-pack"))
    ap.add_argument("--fleet", help="a proposed fleet manifest to assess instead of the deployed one")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any control, red-team case or page alert fails")
    args = ap.parse_args()
    if args.fleet:
        os.environ["FLEET_FILE"] = str(Path(args.fleet).resolve())      # the suite subprocess inherits it
    from assurance_kit.fleet import load_fleet
    from assurance_kit.pack import build_pack, verify_pack
    summary = build_pack(args.out, fleet=load_fleet(), suite=HERE / "compliance")
    summary["verified"] = not verify_pack(args.out)
    print(json.dumps(summary, indent=1))
    alerts = json.loads((Path(args.out) / "alerts.json").read_text(encoding="utf-8"))
    blocked = (not summary["suite_passed"] or summary["redteam"].split("/")[0] != summary["redteam"].split("/")[1]
               or any(a["severity"] == "page" for a in alerts))
    print(f"\nDashboard: {Path(args.out) / 'dashboard.html'}\nScorecard: {Path(args.out) / 'scorecard.md'}")
    return 1 if (args.strict and blocked) else 0


if __name__ == "__main__":
    sys.exit(main())
