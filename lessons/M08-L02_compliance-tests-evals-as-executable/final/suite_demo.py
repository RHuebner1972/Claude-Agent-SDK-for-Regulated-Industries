"""
M08-L02: compliance tests as executable controls. Run the fleet suite twice: as configured, and with one control
switched off in a proposed manifest. Then read the results file CI keeps as evidence.

    uv run python lessons/M08-L02_compliance-tests-evals-as-executable/final/suite_demo.py
"""
from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from pathlib import Path

from sentinel.evidence import run_suite
from sentinel.monitoring.fleet import FLEET_PATH, SENTINEL


def proposed_manifest(change: tuple[str, str]) -> Path:
    """A copy of fleet.yaml with one edit, config paths made absolute so the copy still finds them."""
    text = FLEET_PATH.read_text(encoding="utf-8").replace(*change, 1)
    text = re.sub(r"configs: \[([a-z_/.]+)\]", lambda m: f"configs: [{(SENTINEL / m.group(1)).as_posix()}]", text)
    path = Path(tempfile.mkdtemp()) / "proposed-fleet.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def show(title: str, results: dict) -> None:
    rs = results["results"]
    print(f"\n{title}: exit status {results['exit_status']} "
          f"({sum(r['outcome'] == 'passed' for r in rs)}/{len(rs)} tests passed)")
    covered = sorted({c for r in rs for c in r["controls"]}, key=lambda c: tuple(map(int, c.split("."))))
    print(f"  rubric items evidenced: {len(covered)}  {' '.join(covered)}")
    for r in rs:
        if r["outcome"] != "passed":
            print(f"  FAILED [{', '.join(r['controls'])}] {r['test'].split('::')[1]}\n         {r['message'][:110]}")


def main() -> None:
    work = Path(tempfile.mkdtemp())
    baseline = run_suite(work / "baseline.json")
    show("AS DEPLOYED", baseline)
    print("  by agent:", dict(Counter(r["agent"] or "fleet-wide" for r in baseline["results"])))

    proposed = proposed_manifest(("policy_enforced: true", "policy_enforced: false"))
    show("PROPOSED: complaint-triage with policy_enforced: false",
         run_suite(work / "proposed.json", env={"FLEET_FILE": str(proposed)}))

    print("\nEach result in compliance-results.json:")
    print(json.dumps(baseline["results"][0], indent=1))


if __name__ == "__main__":
    main()
