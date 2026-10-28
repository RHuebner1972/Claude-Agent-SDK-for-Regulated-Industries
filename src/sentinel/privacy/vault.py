"""A reversible token vault: tokenize identifiers, and re-identify only for authorized roles and purposes.

Tokens are deterministic per value (keyed HMAC), so "[[PERSON_1a2b3c4d]]" means the same patient everywhere,
and the model can reason about "this patient" without ever seeing who it is. Values are stored encrypted
(Fernet). Re-identification checks a role -> purposes policy and is written to the audit log, granted or not.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from sentinel.audit import Actor, AgentInfo, AuditEvent, AuditStore, content_version

TOKEN_RE = re.compile(r"\[\[([A-Z_]+)_([0-9a-f]{8})\]\]")


class ReidentificationDenied(PermissionError):
    pass


class ReidPolicy(BaseModel):
    """Who may re-identify, and for what purpose (HIPAA: treatment, payment, operations; plus investigations)."""
    allowed: dict[str, list[str]] = Field(default_factory=lambda: {
        "care_manager": ["treatment", "payment"],
        "utilization_reviewer": ["payment"],
        "privacy_officer": ["investigation"],
    })

    def permits(self, role: str, purpose: str) -> bool:
        return purpose in self.allowed.get(role, [])


class TokenVault:
    def __init__(self, path: str | Path, *, enc_key: bytes | None = None, hmac_key: bytes | None = None,
                 policy: ReidPolicy | None = None, audit: AuditStore | None = None):
        self.path = Path(path)
        self._fernet = Fernet(enc_key or os.environ["VAULT_ENC_KEY"].encode())
        self._hmac_key = hmac_key or os.environ["VAULT_HMAC_KEY"].encode()
        self.policy = policy or ReidPolicy()
        self.audit = audit
        self._lock = threading.Lock()
        self._data: dict[str, dict] = json.loads(self.path.read_text()) if self.path.exists() else {}
        self._agent = AgentInfo(name="token-vault", version="1.0.0", model="n/a", prompt_version="n/a",
                                policy_version=content_version(self.policy.model_dump_json()))

    # -- tokenize: anyone in the pipeline can do this -------------------------------------------
    def tokenize(self, value: str, entity: str) -> str:
        digest = hmac.new(self._hmac_key, f"{entity}|{value}".encode(), hashlib.sha256).hexdigest()[:8]
        token = f"[[{entity}_{digest}]]"
        with self._lock:
            if token not in self._data:
                self._data[token] = {"entity": entity, "value": self._fernet.encrypt(value.encode()).decode(),
                                     "created": datetime.now(timezone.utc).isoformat()}
                self._save()
        return token

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=1))
        tmp.replace(self.path)

    # -- detokenize: only for authorized roles and purposes, always audited ---------------------
    def detokenize(self, token: str, *, requester: str, role: str, purpose: str) -> str:
        call_id = f"reid_{uuid.uuid4().hex[:12]}"
        self._log("tool.requested", requester, call_id, token, purpose, role, outcome="requested")
        if not self.policy.permits(role, purpose):
            reason = f"role {role!r} may not re-identify for purpose {purpose!r}"
            self._log("tool.denied", requester, call_id, token, purpose, role, outcome="denied", reason=reason)
            raise ReidentificationDenied(reason)
        entry = self._data.get(token)
        if entry is None:
            self._log("tool.failed", requester, call_id, token, purpose, role, outcome="error", reason="unknown token")
            raise KeyError(token)
        value = self._fernet.decrypt(entry["value"].encode()).decode()
        self._log("tool.completed", requester, call_id, token, purpose, role, outcome="success",
                  authority=f"ReidPolicy: {role} -> {purpose}")
        return value

    def reidentify_text(self, text: str, *, requester: str, role: str, purpose: str) -> str:
        return TOKEN_RE.sub(lambda m: self.detokenize(m.group(0), requester=requester, role=role, purpose=purpose), text)

    def _log(self, event_type: str, requester: str, call_id: str, token: str, purpose: str, role: str, *,
             outcome: str, reason: str | None = None, authority: str | None = None) -> None:
        if self.audit is None:
            return
        self.audit.append(AuditEvent(
            event_type=event_type, actor=Actor(kind="human", id=requester), on_behalf_of=requester,
            agent=self._agent, tool_name="vault.detokenize", tool_use_id=call_id, outcome=outcome,
            reason=reason, authority=authority, correlation_id=call_id,
            detail={"token": token, "role": role, "purpose": purpose},   # the token, never the value
        ))


def new_keys() -> tuple[str, str]:
    """Generate VAULT_ENC_KEY and VAULT_HMAC_KEY values for .env (demo only; use a KMS in production)."""
    return Fernet.generate_key().decode(), os.urandom(32).hex()
