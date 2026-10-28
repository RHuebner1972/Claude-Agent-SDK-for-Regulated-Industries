"""Lab 2: wire the PHI-safe pipeline together: audit store, token vault, privacy redactor, minimized tools."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from course_data import MODEL, prior_auth_criteria
from sentinel.audit import AgentInfo, AuditHooks, AuditStore, content_version

from phi_guard.mask import PrivacyRedactor
from phi_guard.pa_tools import build_pa_tools
from phi_guard.vault import TokenVault

DEMO_ENC_KEY = "-Uy-ScvZo6q_h-S4bpRwdIU26Fk-Bo4eDb2vC6iVUr0="     # course demo only
SYSTEM_PROMPT = (
    "You are a prior-authorization review ASSISTANT for Northshore Health Plan. For each pending request, call "
    "get_prior_auth_case, compare it with the criteria, and call record_pa_recommendation with approve, deny or "
    "pend, the criterion number and a short clinical rationale. Patient identifiers appear as [[TOKENS]]: refer "
    "to the patient only by token and never try to guess who they are. A licensed clinician makes the final "
    "determination.\n\nCriteria:\n" + prior_auth_criteria()
)
AGENT = AgentInfo(name="PA-Reviewer", version="1.0.0", model=MODEL, prompt_version=content_version(SYSTEM_PROMPT),
                  policy_version=content_version(prior_auth_criteria()))


@dataclass
class Pipeline:
    store: AuditStore
    vault: TokenVault
    hooks: AuditHooks
    tools: list
    recorded: list[dict] = field(default_factory=list)


def build_pipeline(workspace: Path, *, user: str = "n.alvarez") -> Pipeline:
    # TODO 8: wire it together (see the lab instructions for the exact objects).
    # AuditStore(workspace/"audit.jsonl", hmac_key=..., checkpoint_every=25); TokenVault(workspace/"vault.json",
    # enc_key, hmac_key, audit=AuditStore(workspace/"vault_audit.jsonl")); AuditHooks(..., decision_tool=
    # "record_pa_recommendation", redactor=PrivacyRedactor("token", vault)) for the LOG boundary;
    # build_pa_tools(minimized=True, vault=vault, recorded=recorded) for the TOOL boundary. Return a Pipeline.
    raise NotImplementedError("Lab 2: build_pipeline")
