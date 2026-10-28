"""
M04-L06: mask at the tool boundary, the log boundary, or both? Run the same review three ways and count
the identifiers that reach the model and the audit log.

    uv run python lessons/M04-L06_masking-at-the-tool-boundary-vs-the-log/final/boundaries_demo.py
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from course_data import patients
from sentinel.audit import AgentInfo, AuditHooks, AuditStore
from sentinel.privacy import PrivacyRedactor, TokenVault, canaries_from, new_keys, scan_text
from sentinel.privacy.pa_tools import build_pa_tools, simulate_pa_review

AGENT = AgentInfo(name="PA-Reviewer", version="0.4.0", model="claude-sonnet-5-5",
                  prompt_version="sha256:7c1e0a93b2d4", policy_version="sha256:3a8f61c0d9e2")
CONFIGS = [
    ("A. no masking (M03 key redaction only)", False, False),
    ("B. log boundary only", False, True),
    ("C. tool boundary + log boundary", True, True),
]


async def run(minimized: bool, log_masking: bool) -> tuple[str, str]:
    work = Path(tempfile.mkdtemp())
    enc_key, hmac_key = new_keys()
    vault = TokenVault(work / "vault.json", enc_key=enc_key.encode(), hmac_key=hmac_key.encode())
    store = AuditStore(work / "audit.jsonl")
    extra = {"redactor": PrivacyRedactor("token", vault)} if log_masking else {}
    hooks = AuditHooks(store, agent=AGENT, on_behalf_of="n.alvarez", decision_tool="record_pa_recommendation", **extra)
    seen = await simulate_pa_review(hooks, build_pa_tools(minimized=minimized, vault=vault if minimized else None))
    return json.dumps(seen), store.path.read_text(encoding="utf-8")


def main() -> None:
    canaries = canaries_from(patients())
    print(f"{'Configuration':<40} {'Model saw':>10} {'Audit log':>10}")
    for label, minimized, log_masking in CONFIGS:
        model_text, log_text = asyncio.run(run(minimized, log_masking))
        print(f"{label:<40} {len(scan_text(model_text, canaries)):>10} {len(scan_text(log_text, canaries)):>10}")
    print("\nCounts are distinct identifiers (name, MRN, SSN, DOB...) across 8 patients.")


if __name__ == "__main__":
    main()
