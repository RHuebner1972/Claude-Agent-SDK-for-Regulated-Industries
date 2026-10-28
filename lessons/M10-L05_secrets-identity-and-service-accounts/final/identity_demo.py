"""
M10-L05: secrets, identity and service accounts. The agent runs as its own workload identity, credentials expire in
minutes and carry only the scopes one task needs, and they're added outside the sandbox, so the model never sees one.

    uv run python lessons/M10-L05_secrets-identity-and-service-accounts/final/identity_demo.py
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from sentinel.deploy import (CredentialError, CredentialInjector, TokenBroker, WorkloadIdentity, load_deployment,
                             scan_for_secrets)
from sentinel.monitoring.fleet import load_fleet
from sentinel.monitoring.runs import run_agent

AGENT = "aml-triage"


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


def main() -> None:
    dep = load_deployment().get(AGENT)
    ident = dep.identity
    print(f"1. THE IDENTITY: {ident.principal} via {ident.provider}, max {ident.max_ttl_s // 60} min, scopes {ident.scopes}")
    print(f"   upstream secret: {ident.secret_source}")
    try:
        WorkloadIdentity(**{**ident.model_dump(), "principal": "dana.okafor@bayside.example"})
    except ValidationError as exc:
        print(f"   running the agent as a person: refused -> {exc.errors()[0]['msg'][:80]}")

    print("\n2. THE BROKER: short-lived, scoped tokens (a local stand-in for STS / workload identity federation)")
    clock = Clock()
    broker = TokenBroker(b"demo-signing-key", clock=clock)
    token = broker.issue(ident, ["alerts:read"], 300, task="triage ALR-7781")
    print(f"   issued {token.value[:32]}...  scopes {list(token.scopes)}  expires {token.expires_at:%H:%M} UTC")
    for label, call in [("ask for admin:*", lambda: broker.issue(ident, ["admin:*"], 300, task="x")),
                        ("ask for 1 hour", lambda: broker.issue(ident, ["alerts:read"], 3600, task="x")),
                        ("use it to write a case note", lambda: broker.verify(token.value, "cases:note"))]:
        try:
            call()
            print(f"   {label}: allowed (unexpected)")
        except CredentialError as exc:
            print(f"   {label}: refused -> {exc}")
    clock.now += timedelta(minutes=6)
    try:
        broker.verify(token.value, "alerts:read")
    except CredentialError as exc:
        print(f"   six minutes later: {exc}")

    print("\n3. THE INJECTOR: the credential is added after the request leaves the agent's sandbox")
    injector = CredentialInjector(broker, ident, {"core-banking.bayside.example": "alerts:read"})
    headers = injector.outbound("core-banking.bayside.example", {"Accept": "application/json"}, task="ALR-7781")
    print(f"   agent sent: {{'Accept': 'application/json'}}  ->  upstream got Authorization: Bearer {headers['Authorization'][7:27]}...")
    try:
        injector.outbound("core-banking.bayside.example", {"Authorization": "Bearer sk-ant-stolen-0000000000"}, "x")
    except CredentialError as exc:
        print(f"   agent supplies its own credential: refused -> {exc}")

    print("\n4. PROVE IT: scan the run's audit log and a leaky log for credential-shaped strings")
    work = Path(tempfile.mkdtemp())
    run = run_agent(load_fleet().get(AGENT), work / "run")
    print(f"   {AGENT} audit log: {scan_for_secrets([run.general_log]) or 'clean'}")
    leaky = work / "debug.log"
    leaky.write_text(f"calling core banking with {headers['Authorization']}\nAWS key AKIAIOSFODNN7EXAMPLE\n")
    for finding in scan_for_secrets([leaky]):
        print(f"   {finding.replace(str(work), '<tmp>')}")


if __name__ == "__main__":
    main()
