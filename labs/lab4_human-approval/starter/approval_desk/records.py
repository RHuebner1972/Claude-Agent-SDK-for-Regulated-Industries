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
    # TODO 2: build the electronic signature (Part 11.50 manifestation + 11.70 linking).
    # record_sha = record_digest(request); who = {user, name, role, auth_method} from the signer.
    # mac = sign(key, _payload(record_sha, who, meaning, request.meaning_text, reason, signed_at)).
    # Return Signature(user, name, role, meaning, meaning_text=request.meaning_text, reason, signed_at,
    # auth_method, record_sha256=record_sha, hmac=mac).
    raise NotImplementedError("Lab 4: make_signature")


def verify_signature(request: ApprovalRequest, signature: Signature, key: bytes) -> bool:
    """True only if the record is unchanged since signing AND the signature itself is unaltered."""
    # TODO 3: True only if (a) record_digest(request) still equals signature.record_sha256 (the record
    # wasn't edited after signing) AND (b) signature_ok(key, _payload(...same fields from the signature...), signature.hmac)
    # (the signature itself wasn't edited).
    raise NotImplementedError("Lab 4: verify_signature")
