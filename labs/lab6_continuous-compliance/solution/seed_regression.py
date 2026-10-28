"""
Write a PROPOSED fleet manifest with one seeded regression, to prove the pipeline catches it.

    uv run python seed_regression.py masking            # -> out/proposed-fleet.yaml
    uv run python assure.py --fleet out/proposed-fleet.yaml --strict      # exit 1: the build fails
    FLEET_FILE=out/proposed-fleet.yaml uv run pytest compliance           # or just the suite
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGRESSIONS = {
    "masking":  ("pa-reviewer", "controls: {audit_hmac: true, minimized_tools: true, log_masking: token}",
                 "controls: {audit_hmac: true, minimized_tools: false, log_masking: null}",
                 "a prompt-template refactor dropped both PHI controls"),
    "policy":   ("complaint-triage", "controls: {audit_hmac: true, policy_enforced: true}",
                 "controls: {audit_hmac: true, policy_enforced: false}", "policy hook removed 'to debug a timeout'"),
    "approval": ("aml-triage", "controls: {audit_hmac: true, approval_gate: deny}",
                 "controls: {audit_hmac: true, approval_gate: null}", "approval gate disabled for a demo"),
    "contract": ("ccb-assistant", "controls: {audit_hmac: true, handoff_contracts: true, routed_logs: true}",
                 "controls: {audit_hmac: true, handoff_contracts: false, routed_logs: true}",
                 "handoff contract switched off 'because summaries were too terse'"),
    "model":    ("ledgerbot", "model: claude-sonnet-5-5\n    prompt_version: sha256:5d41c0a19e2b",
                 "model: claude-sonnet-5-6\n    prompt_version: sha256:5d41c0a19e2b", "model upgraded without a change record"),
}


def seed(name: str, out: Path | None = None) -> Path:
    from assurance_kit.fleet import FLEET_PATH, SENTINEL
    agent, old, new, why = REGRESSIONS[name]
    text = FLEET_PATH.read_text(encoding="utf-8")
    assert old in text, f"manifest no longer contains: {old}"
    text = text.replace(old, new, 1)
    text = re.sub(r"configs: \[([a-z_/.]+)\]", lambda m: f"configs: [{(SENTINEL / m.group(1)).as_posix()}]", text)
    out = out or HERE / "out" / "proposed-fleet.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# PROPOSED CHANGE (seeded regression '{name}'): {agent}: {why}\n" + text, encoding="utf-8")
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "masking"
    print(seed(which))
