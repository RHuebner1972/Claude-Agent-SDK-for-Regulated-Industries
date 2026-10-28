"""Approval records as electronic signatures: build them, and prove later that nothing changed.

Signature manifestation (21 CFR 11.50): printed name, date and time, and meaning, as part of the record.
Signature/record linking (11.70): the signature carries a hash of the exact record, and an HMAC over both,
so it can't be cut from one approval and pasted onto another, and an edited record no longer verifies.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal

from sentinel.audit.hashing import canonical, sign, signature_ok

from .models import ApprovalRequest, Signature, Signer


def input_digest(tool: str, tool_input: dict[str, Any]) -> str:
    """Binds an approval to ONE exact call: change the amount or the account and it's a different action."""
    return "sha256:" + hashlib.sha256(canonical({"tool": tool, "input": tool_input})).hexdigest()


def record_digest(request: ApprovalRequest) -> str:
    return "sha256:" + hashlib.sha256(canonical(request.record_core())).hexdigest()


def _payload(record_sha256: str, signer: dict, meaning: str, meaning_text: str, reason: str, signed_at: datetime) -> str:
    return canonical({"record_sha256": record_sha256, "signer": signer, "meaning": meaning,
                      "meaning_text": meaning_text, "reason": reason,
                      "signed_at": signed_at.isoformat()}).decode("utf-8")


def make_signature(request: ApprovalRequest, signer: Signer, meaning: Literal["approve", "reject"], reason: str,
                   signed_at: datetime, key: bytes) -> Signature:
    record_sha = record_digest(request)
    who = {"user": signer.user, "name": signer.name, "role": signer.role, "auth_method": signer.auth_method}
    mac = sign(key, _payload(record_sha, who, meaning, request.meaning_text, reason, signed_at))
    return Signature(user=signer.user, name=signer.name, role=signer.role, meaning=meaning,
                     meaning_text=request.meaning_text, reason=reason, signed_at=signed_at,
                     auth_method=signer.auth_method, record_sha256=record_sha, hmac=mac)


def verify_signature(request: ApprovalRequest, signature: Signature, key: bytes) -> bool:
    """True only if the record is unchanged since signing AND the signature itself is unaltered."""
    if record_digest(request) != signature.record_sha256:
        return False
    who = {"user": signature.user, "name": signature.name, "role": signature.role,
           "auth_method": signature.auth_method}
    return signature_ok(key, _payload(signature.record_sha256, who, signature.meaning, signature.meaning_text,
                                      signature.reason, signature.signed_at), signature.hmac)
