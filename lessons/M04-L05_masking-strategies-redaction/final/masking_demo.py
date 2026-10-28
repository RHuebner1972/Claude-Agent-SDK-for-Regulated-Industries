"""
M04-L05: five masking strategies on the same note, then a reversible token vault with access control.

    uv run python lessons/M04-L05_masking-strategies-redaction/final/masking_demo.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from course_data import patients, prior_auth_requests
from sentinel.audit import AuditStore
from sentinel.privacy import ReidentificationDenied, TokenVault, known_values, mask_text, new_keys


def main() -> None:
    req = next(r for r in prior_auth_requests() if r["request_id"] == "PA-2007")
    patient = next(p for p in patients() if p["patient_id"] == req["patient_id"])
    known = known_values(patient)
    print("Original:\n ", req["clinical_notes"], "\n")

    work = Path(tempfile.mkdtemp())
    enc_key, hmac_key = new_keys()                    # demo keys; production keys live in a KMS
    vault = TokenVault(work / "vault.json", enc_key=enc_key.encode(), hmac_key=hmac_key.encode(),
                       audit=AuditStore(work / "vault_audit.jsonl"))
    for strategy in ("redact", "partial", "pseudonym", "generalize", "token"):
        masked = mask_text(req["clinical_notes"], strategy, vault=vault, known=known).text
        print(f"{strategy:<11} {masked}\n")

    tokenized = mask_text(req["clinical_notes"], "token", vault=vault, known=known).text
    print("Vault file holds ciphertext only:", patient["last_name"] not in (work / "vault.json").read_text())

    print("\nRe-identification requests:")
    for requester, role, purpose in [("k.osei", "care_manager", "treatment"), ("d.ruiz", "data_analyst", "analytics"),
                                     ("m.chen", "utilization_reviewer", "treatment")]:
        try:
            text = vault.reidentify_text(tokenized, requester=requester, role=role, purpose=purpose)
            print(f"  GRANTED {requester} ({role}, {purpose}): {text[:48]}...")
        except ReidentificationDenied as exc:
            print(f"  DENIED  {requester}: {exc}")

    events = AuditStore(work / "vault_audit.jsonl").records()
    print(f"\nVault audit log: {len(events)} events, "
          f"{sum(e['event_type'] == 'tool.denied' for e in events)} denials, every one with requester, role and purpose")


if __name__ == "__main__":
    main()
