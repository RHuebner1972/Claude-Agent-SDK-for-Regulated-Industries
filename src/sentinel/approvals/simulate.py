"""Offline driver: play a scripted triage through the gate, pausing on 'defer' exactly as the SDK would.

The SDK's defer round trip: the PreToolUse hook returns "defer", the run stops with
ResultMessage.stop_reason == "tool_deferred" and deferred_tool_use = {id, name, input}. Later the app resumes
the same session; the same tool call fires PreToolUse again, and this time the gate finds the approval.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from claude_agent_sdk import ResultMessage
from claude_agent_sdk.types import DeferredToolUse

from .aml_tools import full_name


class FixedClock:
    """A clock you control: each read moves it forward a little; advance() jumps ahead (minutes)."""
    def __init__(self, start: str = "2026-10-15T13:00:00+00:00", step_seconds: float = 5):
        self.now = datetime.fromisoformat(start).astimezone(timezone.utc)
        self.step = timedelta(seconds=step_seconds)

    def __call__(self) -> datetime:
        self.now += self.step
        return self.now

    def advance(self, minutes: float) -> None:
        self.now += timedelta(minutes=minutes)


@dataclass
class Step:
    tool: str
    args: dict[str, Any]
    outcome: str = ""          # executed | denied | deferred | stopped
    message: str = ""


@dataclass
class RunLog:
    steps: list[Step] = field(default_factory=list)
    paused_at: int | None = None          # index of the deferred step; resume from here
    deferred: DeferredToolUse | None = None

    @property
    def executed(self) -> list[str]:
        return [f"{s.tool} {s.args.get('alert_id', '')}".strip() for s in self.steps if s.outcome == "executed"]

    def table(self) -> str:
        return "\n".join(f"  {s.outcome.upper():8} {s.tool:21} {s.args.get('alert_id', ''):9} "
                         f"{s.message if s.outcome != 'executed' else ''}" for s in self.steps)


async def run_script(tools, script: list[tuple[str, dict]], *, gate=None, audit=None, start: int = 0,
                     session_id: str = "sess-aml-6b20", prompt: str = "Triage my open AML alerts.") -> RunLog:
    by_name = {t.name: t for t in tools}
    gates = gate if isinstance(gate, (list, tuple)) else ([gate] if gate else [])
    base = {"session_id": session_id, "transcript_path": f"~/.claude/projects/aml/{session_id}.jsonl",
            "cwd": "/srv/aml", "permission_mode": "dontAsk"}
    log = RunLog()
    if audit and start == 0:
        await audit.on_prompt({**base, "hook_event_name": "UserPromptSubmit", "prompt": prompt}, None, {"signal": None})
    for i in range(start, len(script)):
        name, args = script[i]
        tid = f"toolu_{session_id[-4:]}_{i:03d}"          # stable: a resumed call keeps its tool_use_id
        pre_in = {**base, "hook_event_name": "PreToolUse", "tool_name": full_name(name), "tool_input": args,
                  "tool_use_id": tid}
        out: dict = {}
        if audit:
            out = await audit.on_pre_tool(pre_in, tid, {"signal": None})
        for g in gates:                                   # chained in order; the first deny wins
            if out.get("hookSpecificOutput", {}).get("permissionDecision"):
                break
            out = await g.pre_tool_use(pre_in, tid, {"signal": None})
        hso = out.get("hookSpecificOutput", {})
        decision = hso.get("permissionDecision")
        step = Step(name, args)
        log.steps.append(step)
        if out.get("continue_") is False:                 # kill switch: the whole run stops here
            step.outcome, step.message = "stopped", out.get("stopReason", "")
            return log
        if decision in ("deny", "defer"):
            step.outcome = "denied" if decision == "deny" else "deferred"
            step.message = hso.get("permissionDecisionReason", "")
            if decision == "defer":
                log.paused_at, log.deferred = i, DeferredToolUse(id=tid, name=full_name(name), input=args)
                if audit:
                    audit.observe(ResultMessage(subtype="success", duration_ms=9000, duration_api_ms=7000,
                                                is_error=False, num_turns=i + 1, session_id=session_id,
                                                stop_reason="tool_deferred", deferred_tool_use=log.deferred,
                                                terminal_reason="tool_deferred"))
                return log
            continue
        result = await by_name[name].handler(args)
        post_in = {**base, "hook_event_name": "PostToolUse", "tool_name": full_name(name), "tool_input": args,
                   "tool_response": result, "tool_use_id": tid, "duration_ms": 30}
        if audit:
            await audit.on_post_tool(post_in, tid, {"signal": None})
        for g in gates:
            if hasattr(g, "post_tool_use"):
                await g.post_tool_use(post_in, tid, {"signal": None})
        step.outcome = "error" if result.get("is_error") else "executed"
        step.message = result["content"][0]["text"]
    if audit:
        await audit.on_stop({**base, "hook_event_name": "Stop", "stop_hook_active": False,
                             "last_assistant_message": "Triage finished.\n" + log.table()}, None, {"signal": None})
        audit.observe(ResultMessage(subtype="success", duration_ms=21000, duration_api_ms=16000, is_error=False,
                                    num_turns=len(script), session_id=session_id, terminal_reason="completed"))
    return log


TRIAGE: list[tuple[str, dict]] = [
    ("list_alerts", {}),
    ("get_alert", {"alert_id": "ALR-5002"}),
    ("close_alert", {"alert_id": "ALR-5002", "disposition": "false_positive",
                     "rationale": "Bi-weekly ACH to the same payroll processor since 2015; amounts match payroll."}),
    ("get_alert", {"alert_id": "ALR-5001"}),
    ("recommend_sar", {"alert_id": "ALR-5001", "activity_type": "structuring", "suspicious_amount": 57800,
                       "narrative": "Six cash deposits of $9,300-$9,900 in 8 days across three branches; "
                                    "expected cash is about $4,000 a month. Pattern consistent with structuring."}),
    ("get_alert", {"alert_id": "ALR-5003"}),
    ("restrict_account", {"alert_id": "ALR-5003", "account_id": "ACC-77345", "restriction": "block_outgoing_wires",
                          "reason": "Funds from three unrelated senders moved to a crypto exchange within 24 hours."}),
    ("get_alert", {"alert_id": "ALR-5007"}),
    ("add_case_note", {"alert_id": "ALR-5007", "note": "Purpose of the round-dollar transfers is unclear; "
                                                      "asked the relationship manager for an explanation."}),
]
