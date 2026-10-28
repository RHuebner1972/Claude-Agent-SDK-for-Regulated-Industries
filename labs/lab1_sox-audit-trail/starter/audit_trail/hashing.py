"""Canonical JSON and SHA-256: the same event must always produce the same bytes and the same hash."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

GENESIS = "0" * 64  # prev_hash of the very first event in a log


def canonical(data: Any) -> bytes:
    """Sorted keys, no whitespace, UTF-8: one byte string per logical value."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")


def sha256_hex(data: Any) -> str:
    return hashlib.sha256(canonical(data)).hexdigest()


def record_hash(record: dict[str, Any]) -> str:
    """Hash of an event record: every field except 'hash' itself (prev_hash IS included, which makes the chain)."""
    return sha256_hex({k: v for k, v in record.items() if k != "hash"})


def sign(key: bytes, message: str) -> str:
    """HMAC-SHA256. Anyone can recompute a plain hash; only a key holder can produce this."""
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).hexdigest()


def signature_ok(key: bytes, message: str, signature: str) -> bool:
    return hmac.compare_digest(sign(key, message), signature)
