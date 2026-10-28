"""Helpers shared by the course lessons: synthetic data loaders, the pinned model and a message printer."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "synthetic"

# Pin the exact model your organization approved. Override with COURSE_MODEL; check Anthropic's
# models page for current IDs. A pinned model is a validated configuration (Module 8 covers changes).
MODEL = os.getenv("COURSE_MODEL", "claude-sonnet-5-5")


def _finance(name: str):
    return json.loads((DATA_DIR / "finance" / f"{name}.json").read_text(encoding="utf-8"))


def journal_entries() -> list[dict]:
    return _finance("journal_entries")


def vendors() -> list[dict]:
    return _finance("vendors")


def gl_accounts() -> list[dict]:
    return _finance("gl_accounts")


def approval_policy() -> str:
    return (DATA_DIR / "finance" / "approval_policy.md").read_text(encoding="utf-8")


def _health(name: str):
    return json.loads((DATA_DIR / "healthcare" / f"{name}.json").read_text(encoding="utf-8"))


def patients() -> list[dict]:
    return _health("patients")


def providers() -> list[dict]:
    return _health("providers")


def prior_auth_requests() -> list[dict]:
    return _health("prior_auth_requests")


def phi_annotations() -> dict[str, list[dict]]:
    return _health("phi_annotations")


def prior_auth_criteria() -> str:
    return (DATA_DIR / "healthcare" / "prior_auth_criteria.md").read_text(encoding="utf-8")


def complaints() -> list[dict]:
    return json.loads((DATA_DIR / "devices" / "complaints.json").read_text(encoding="utf-8"))


def complaint_procedure() -> str:
    return (DATA_DIR / "devices" / "complaint_procedure.md").read_text(encoding="utf-8")


def _aml(name: str):
    return json.loads((DATA_DIR / "aml" / f"{name}.json").read_text(encoding="utf-8"))


def aml_alerts() -> list[dict]:
    return _aml("alerts")


def aml_staff() -> list[dict]:
    return _aml("staff")


def aml_procedure() -> str:
    return (DATA_DIR / "aml" / "disposition_procedure.md").read_text(encoding="utf-8")


def _defense(name: str):
    return json.loads((DATA_DIR / "defense" / f"{name}.json").read_text(encoding="utf-8"))


def ecrs() -> list[dict]:
    return _defense("ecrs")


def programs() -> dict:
    return _defense("programs")


def change_procedure() -> str:
    return (DATA_DIR / "defense" / "change_procedure.md").read_text(encoding="utf-8")


from .show import show  # noqa: E402

__all__ = ["MODEL", "REPO_ROOT", "DATA_DIR", "journal_entries", "vendors", "gl_accounts", "approval_policy",
           "patients", "providers", "prior_auth_requests", "phi_annotations", "prior_auth_criteria",
           "complaints", "complaint_procedure", "aml_alerts", "aml_staff", "aml_procedure", "ecrs",
           "programs", "change_procedure", "show"]
