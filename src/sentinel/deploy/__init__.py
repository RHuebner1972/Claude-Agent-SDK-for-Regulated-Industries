"""Production deployment controls (M10): where Claude runs, retention and deletion, identity, and the sandbox.

    python -m sentinel.deploy paths --phi --fedramp high       # shortlist deployment paths for requirements
    python -m sentinel.deploy preflight                        # check deployment.yaml against the fleet
    python -m sentinel.deploy docker aml-triage                # the hardened `docker run` for one agent
    python -m sentinel.deploy reference deploy/reference --agent aml-triage   # check the reference architecture
"""
from .deployment import (AgentDeployment, AuditStorage, Deployment, check_agent, check_reference, load_deployment,
                         preflight)
from .identity import (CredentialError, CredentialInjector, Token, TokenBroker, WorkloadIdentity,
                       scan_for_secrets)
from .paths import Fit, PathCatalog, Requirements, load_catalog, shortlist
from .retention import (DeletionReceipt, RetentionLocked, RetentionRule, TranscriptStore, WormStore,
                        archive_audit_log, session_options, sweep)
from .sandbox import (EgressDecision, EgressPolicy, FsGuard, SandboxProfile, docker_args, lint_profile,
                      sdk_sandbox_settings)

__all__ = ["AgentDeployment", "AuditStorage", "CredentialError", "CredentialInjector", "DeletionReceipt",
           "Deployment", "EgressDecision", "EgressPolicy", "Fit", "FsGuard", "PathCatalog", "Requirements",
           "RetentionLocked", "RetentionRule", "SandboxProfile", "Token", "TokenBroker", "TranscriptStore",
           "WorkloadIdentity", "WormStore", "archive_audit_log", "check_agent", "check_reference", "docker_args", "lint_profile",
           "load_catalog", "load_deployment", "preflight", "scan_for_secrets", "sdk_sandbox_settings",
           "session_options", "shortlist", "sweep"]
