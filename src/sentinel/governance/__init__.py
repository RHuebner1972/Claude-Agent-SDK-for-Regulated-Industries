"""Governance, validation and board-ready evidence (M11): the AI system inventory, the risk register (FMEA),
validation records, the RACI, agent cards and a board brief generated from the evidence.

    python -m sentinel.governance inventory                    # lint the inventory and list every system
    python -m sentinel.governance card --agent aml-triage      # one agent card
    python -m sentinel.governance risks [--agent NAME]         # the FMEA, severity-first
    python -m sentinel.governance validate                     # validation records: current, stale or missing
    python -m sentinel.governance raci                         # who does what, and independence checks
    python -m sentinel.governance brief --org "Bayside Community Bank"   # runs the suite, then writes the brief
"""
from .brief import (BOARD_QUESTIONS, Claim, Governance, Section, agent_card, board_brief, brief_sections,
                    confirmed_scorecard, evidence_index, lint_all, lint_brief, load_governance, render_brief)
from .inventory import (Assessment, Classification, Inventory, SystemEntry, lint_inventory, load_inventory,
                        required_assessments)
from .raci import Raci, RaciActivity, lint_raci, load_raci, render_raci
from .risk import FailureMode, RiskRegister, lint_register, load_register, priority, render_register
from .validation import (MRM_ELEMENTS, ValidationRecord, ValidationSet, lint_validations, load_validations,
                         status, summary_md)

__all__ = ["BOARD_QUESTIONS", "MRM_ELEMENTS", "Assessment", "Claim", "Classification", "FailureMode", "Governance",
           "Inventory", "Raci", "RaciActivity", "RiskRegister", "Section", "SystemEntry", "ValidationRecord",
           "ValidationSet", "agent_card", "board_brief", "brief_sections", "confirmed_scorecard", "evidence_index",
           "lint_all", "lint_brief", "lint_inventory", "lint_raci", "lint_register", "lint_validations",
           "load_governance", "load_inventory", "load_raci", "load_register", "load_validations", "priority",
           "render_brief", "render_raci", "render_register", "required_assessments", "status", "summary_md"]
