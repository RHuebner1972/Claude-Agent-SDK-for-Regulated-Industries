"""
M03-L02: build an AuditEvent, print it, then watch the model refuse three events an auditor couldn't use.

    uv run python lessons/M03-L02_anatomy-of-an-agent-audit-event-the/final/demo_events.py
"""
from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from audit_models import Actor, AgentInfo, AuditEvent

AGENT = AgentInfo(name="LedgerBot", version="1.3.0", model="claude-sonnet-5-5",
                  prompt_version="sha256:5d41c0a19e2b", policy_version="sha256:9c1e07f3aa42")
COMMON = dict(on_behalf_of="j.chen", agent=AGENT, correlation_id="run-20261001T140000Z-4be1c0de")


def main() -> None:
    event = AuditEvent(
        event_type="decision.recorded",
        actor=Actor(kind="agent", id="LedgerBot@1.3.0"),
        tool_name="mcp__ledger__record_recommendation",
        tool_use_id="toolu_007",
        reason="Amount $62,500 is at or above the $50,000 threshold",
        authority="Policy rule 1",
        detail={"entry_id": "JE-1003", "recommendation": "escalate", "approver_required": "Controller"},
        **COMMON,
    )
    print(event.model_dump_json(indent=2, exclude_none=True))

    bad_events = {
        "naive local timestamp": dict(event_type="prompt.submitted", actor=Actor(kind="human", id="j.chen"),
                                      timestamp=datetime(2026, 10, 1, 9, 0)),
        "tool event with no tool_use_id": dict(event_type="tool.completed", actor=Actor(kind="agent", id="LedgerBot@1.3.0"),
                                               tool_name="mcp__ledger__get_journal_entry"),
        "decision with no authority": dict(event_type="decision.recorded", actor=Actor(kind="agent", id="LedgerBot@1.3.0"),
                                           reason="looks fine"),
        "unknown field (typo)": dict(event_type="agent.stopped", actor=Actor(kind="agent", id="LedgerBot@1.3.0"),
                                     outcom="success"),
    }
    print("\nEvents the model refuses to create:")
    for label, fields in bad_events.items():
        try:
            AuditEvent(**fields, **COMMON)
            print(f"  ACCEPTED (bug!)  {label}")
        except ValidationError as exc:
            print(f"  REJECTED  {label}: {exc.errors()[0]['msg']}")


if __name__ == "__main__":
    main()
