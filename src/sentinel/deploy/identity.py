"""Agent identity and secrets (rubric 3.3, M10-L05): scoped, short-lived, and never held by the agent.

The agent gets its OWN workload identity (never a person's account), credentials expire in minutes, each token
carries only the scopes one task needs, and the credential is added by a broker or proxy OUTSIDE the agent's
sandbox. The model never sees a secret, so a prompt injection can't leak one, and logs can be scanned to prove it.

TokenBroker is a local stand-in for your cloud's token service (AWS STS AssumeRole with session tags, Google
workload identity federation, Microsoft Entra workload identities). It signs tokens with HMAC so the course runs
offline; production uses the cloud service and its own audit trail.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

Clock = Callable[[], datetime]
HUMAN_PRINCIPAL = re.compile(r"^(user:|[^@:]+@[^@]+\.[a-z]{2,}$)", re.I)      # user:..., or a bare email address


class CredentialError(Exception):
    pass


class WorkloadIdentity(BaseModel):
    """Declared in deployment.yaml for each agent."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    principal: str = Field(min_length=5)                 # e.g. "svc:aml-triage@bayside-prod"
    provider: str                                        # "aws-sts", "gcp-wif", "entra-workload", "anthropic-proxy"
    max_ttl_s: int = Field(ge=60, le=3600)
    scopes: list[str] = Field(min_length=1)              # what the agent's tools may do, e.g. "alerts:read"
    secret_source: str = Field(min_length=3)             # where the broker gets the upstream secret

    @field_validator("principal")
    @classmethod
    def _not_a_person(cls, v: str) -> str:
        if not v.startswith("svc:") or HUMAN_PRINCIPAL.match(v):
            raise ValueError(f"{v!r}: an agent runs as a workload principal ('svc:...'), never as a person")
        return v


@dataclass(frozen=True)
class Token:
    value: str
    principal: str
    scopes: tuple[str, ...]
    expires_at: datetime


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class TokenBroker:
    """Issues and verifies short-lived, scoped tokens for agent workloads."""

    def __init__(self, key: bytes, clock: Clock = lambda: datetime.now(timezone.utc)):
        self.key, self.clock = key, clock
        self.issued: list[str] = []                       # token ids, for the broker's own audit trail

    def issue(self, ident: WorkloadIdentity, scopes: list[str], ttl_s: int, *, task: str) -> Token:
        if ttl_s > ident.max_ttl_s:
            raise CredentialError(f"TTL {ttl_s}s exceeds {ident.principal}'s maximum of {ident.max_ttl_s}s")
        extra = sorted(set(scopes) - set(ident.scopes))
        if extra:
            raise CredentialError(f"{ident.principal} isn't granted {extra}")
        exp = self.clock() + timedelta(seconds=ttl_s)
        claims = {"sub": ident.principal, "scp": sorted(scopes), "exp": int(exp.timestamp()), "task": task,
                  "jti": secrets.token_hex(8)}
        body = _b64(json.dumps(claims, sort_keys=True).encode())
        sig = _b64(hmac.new(self.key, body.encode(), hashlib.sha256).digest())
        self.issued.append(claims["jti"])
        return Token(f"sat.{body}.{sig}", ident.principal, tuple(sorted(scopes)), exp)

    def verify(self, value: str, scope: str) -> dict:
        try:
            _, body, sig = value.split(".")
        except ValueError as exc:
            raise CredentialError("malformed token") from exc
        good = _b64(hmac.new(self.key, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise CredentialError("bad signature")
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if self.clock().timestamp() >= claims["exp"]:
            raise CredentialError("token expired")
        if scope not in claims["scp"]:
            raise CredentialError(f"scope {scope!r} not in token")
        return claims


class CredentialInjector:
    """Runs OUTSIDE the agent sandbox (in the egress proxy or the tool server). The agent sends a request with no
    credential; the injector looks up the scope for the destination, gets a fresh token and adds the header."""

    def __init__(self, broker: TokenBroker, ident: WorkloadIdentity, routes: dict[str, str], ttl_s: int = 300):
        self.broker, self.ident, self.routes, self.ttl_s = broker, ident, routes, ttl_s

    def outbound(self, host: str, headers: dict[str, str], task: str) -> dict[str, str]:
        if any(k.lower() in ("authorization", "x-api-key") for k in headers):
            raise CredentialError("the agent tried to supply its own credential: refused, and worth an alert")
        scope = self.routes.get(host)
        if scope is None:
            raise CredentialError(f"no credential route for {host}")
        token = self.broker.issue(self.ident, [scope], self.ttl_s, task=task)
        return {**headers, "Authorization": f"Bearer {token.value}"}


SECRET_PATTERNS = {
    "anthropic_api_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    "aws_access_key_id": re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
    "sentinel_token": re.compile(r"\bsat\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "gcp_service_account": re.compile(r'"type":\s*"service_account"'),
}


def scan_for_secrets(paths: list[str | Path]) -> list[str]:
    """Findings for any credential-shaped string in logs, transcripts or evidence. Empty list = clean."""
    findings = []
    for path in map(Path, paths):
        files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for f in files:
            text = f.read_text(encoding="utf-8", errors="ignore")
            for name, pat in SECRET_PATTERNS.items():
                if pat.search(text):
                    findings.append(f"SEC-001 {name} in {f}")
    return findings
