"""Logging without leaking: what goes in the audit log is a redacted summary plus a fingerprint.

Hash, don't hoard: store sha256 of the full tool response so you can PROVE what the agent saw
(by re-hashing the source record) without copying sensitive data into a second system.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .hashing import sha256_hex

SENSITIVE_KEYS = {
    "bank_account", "account_number", "routing_number", "iban", "tax_id", "ssn", "dob",
    "password", "api_key", "secret", "token", "authorization",
}
LONG_NUMBER = re.compile(r"\b\d{9,}\b")          # account-like digit runs
TAX_ID = re.compile(r"\b\d{2}-\d{7}\b")          # EIN pattern
REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Recursively blank sensitive keys and mask account-like numbers in strings."""
    if isinstance(value, dict):
        return {k: (REDACTED if k.lower() in SENSITIVE_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return TAX_ID.sub(REDACTED, LONG_NUMBER.sub(REDACTED, value))
    return value


def response_text(tool_response: Any) -> Any:
    """SDK tool responses arrive as MCP content blocks; pull out the text and parse JSON if it is JSON."""
    if isinstance(tool_response, dict) and "content" in tool_response:
        tool_response = tool_response["content"]
    if isinstance(tool_response, list):
        texts = [b.get("text", "") for b in tool_response if isinstance(b, dict) and b.get("type") == "text"]
        if texts:
            tool_response = "\n".join(texts)
    if isinstance(tool_response, str):
        try:
            return json.loads(tool_response)
        except ValueError:
            return tool_response
    return tool_response


def summarize(value: Any, limit: int = 300) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def fingerprint(value: Any) -> str:
    return "sha256:" + sha256_hex(value)
