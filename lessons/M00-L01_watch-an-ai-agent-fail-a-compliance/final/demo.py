"""
M00-L01 cold open: the same prior-authorization agent, built two ways.

    uv run python lessons/M00-L01_watch-an-ai-agent-fail-a-compliance/final/demo.py --mode naive
    uv run python lessons/M00-L01_watch-an-ai-agent-fail-a-compliance/final/demo.py --mode hardened

Naive:    the way most agent tutorials build it. Full record, debug logging, every tool auto-approved.
Hardened: a preview of this course. Minimum-necessary data, masked hash-chained audit trail,
          and a human who must approve the decision before it is recorded.

All patient data in this file is synthetic.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolPermissionContext,
    create_sdk_mcp_server,
    tool,
)

OUT = Path(__file__).parent / "output"

# --------------------------------------------------------------------------- synthetic data
PATIENT = {
    "patient_id": "P-1001",
    "name": "Maria Delgado",
    "dob": "1968-04-12",
    "ssn": "512-44-8391",
    "mrn": "MRN-00482913",
    "address": "88 Elm Street, Springfield, IL 62701",
    "diagnoses": ["M17.11 Primary osteoarthritis, right knee"],
    "conservative_therapy_weeks": 12,
    "notes": "Failed 12 weeks of physical therapy and NSAIDs. Persistent pain and effusion.",
}
REQUEST = {
    "request_id": "PA-7781",
    "patient_id": "P-1001",
    "service": "MRI right knee (CPT 73721)",
    "criteria": "Approve knee MRI only after 6+ weeks of failed conservative therapy.",
}
# The identifiers we will hunt for in the logs afterwards.
IDENTIFIERS = {k: PATIENT[k] for k in ("name", "dob", "ssn", "mrn", "address")}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask(text: str) -> str:
    """Replace this patient's identifiers (and anything SSN-shaped) with labeled tokens."""
    for label, value in IDENTIFIERS.items():
        text = text.replace(value, f"[{label.upper()}]")
    return re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)


# --------------------------------------------------------------------------- tools
def build_tools(mode: str):
    @tool("get_patient_record", "Fetch the clinical record needed for a prior-authorization review",
          {"patient_id": str})
    async def get_patient_record(args: dict[str, Any]) -> dict[str, Any]:
        if args["patient_id"] != PATIENT["patient_id"]:
            return {"content": [{"type": "text", "text": "No such patient."}], "is_error": True}
        if mode == "naive":
            record = PATIENT  # everything, "so the model has context"
        else:
            # Minimum necessary: only the fields this decision needs (HIPAA 45 CFR 164.502(b)).
            record = {k: PATIENT[k] for k in ("patient_id", "diagnoses", "conservative_therapy_weeks", "notes")}
        return {"content": [{"type": "text", "text": json.dumps(record)}]}

    @tool("record_decision", "Record the prior-authorization decision",
          {"request_id": str, "decision": str, "rationale": str})
    async def record_decision(args: dict[str, Any]) -> dict[str, Any]:
        OUT.mkdir(exist_ok=True)
        with (OUT / f"{mode}_decisions.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now(), **args}) + "\n")
        return {"content": [{"type": "text", "text": f"Decision recorded for {args['request_id']}."}]}

    return [get_patient_record, record_decision]


# --------------------------------------------------------------------------- naive logging
def naive_hooks():
    log = OUT / "naive_debug.log"

    async def debug(input_data, tool_use_id, context):
        with log.open("a", encoding="utf-8") as f:  # raw, unmasked, mutable: a regulator's nightmare
            f.write(f"{now()} {input_data['hook_event_name']} {json.dumps(input_data, default=str)}\n")
        return {}

    m = [HookMatcher(hooks=[debug])]
    return {"UserPromptSubmit": m, "PreToolUse": m, "PostToolUse": m}


# --------------------------------------------------------------------------- hardened audit trail
class AuditTrail:
    """Append-only JSONL where every event carries the hash of the one before it."""

    def __init__(self, path: Path, actor: str):
        self.path, self.actor, self.prev = path, actor, "GENESIS"

    def write(self, event: str, payload: Any) -> None:
        record = {"ts": now(), "actor": self.actor, "event": event,
                  "payload": mask(json.dumps(payload, default=str)), "prev_hash": self.prev}
        record["hash"] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        self.prev = record["hash"]

    @staticmethod
    def verify(path: Path) -> tuple[bool, int]:
        prev, n = "GENESIS", 0
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            claimed = rec.pop("hash")
            if rec["prev_hash"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest() != claimed:
                return False, n
            prev, n = claimed, n + 1
        return True, n


def hardened_hooks(trail: AuditTrail):
    async def on_prompt(input_data, tool_use_id, context):
        trail.write("prompt", {"session": input_data["session_id"], "prompt": input_data["prompt"]})
        return {}

    async def before_tool(input_data, tool_use_id, context):
        trail.write("tool_call", {"tool": input_data["tool_name"], "input": input_data["tool_input"]})
        return {}

    async def after_tool(input_data, tool_use_id, context):
        trail.write("tool_result", {"tool": input_data["tool_name"], "output": input_data["tool_response"]})
        return {}

    return {"UserPromptSubmit": [HookMatcher(hooks=[on_prompt])],
            "PreToolUse": [HookMatcher(hooks=[before_tool])],
            "PostToolUse": [HookMatcher(hooks=[after_tool])]}


def human_approval(trail: AuditTrail, reviewer: str):
    """Any tool not pre-approved lands here. record_decision is deliberately not pre-approved."""

    async def can_use_tool(tool_name: str, tool_input: dict[str, Any], context: ToolPermissionContext):
        print("\n" + "=" * 64)
        print(" HUMAN APPROVAL REQUIRED")
        print(f" Tool:      {tool_name}")
        for k, v in tool_input.items():
            print(f" {k:<10} {v}")
        print("=" * 64)
        answer = await asyncio.to_thread(input, f" {reviewer}, approve this action? [y/N] ")
        approved = answer.strip().lower() == "y"
        trail.write("human_review", {"tool": tool_name, "reviewer": reviewer,
                                     "decision": "approved" if approved else "rejected", "input": tool_input})
        if approved:
            return PermissionResultAllow()
        return PermissionResultDeny(message=f"Rejected by reviewer {reviewer}. Do not retry.", interrupt=True)

    return can_use_tool


# --------------------------------------------------------------------------- scorecard
def phi_hits(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    return {k: text.count(v) for k, v in IDENTIFIERS.items() if text.count(v)}


def scorecard(mode: str, reviewer: str | None) -> None:
    log = OUT / ("naive_debug.log" if mode == "naive" else "hardened_audit.jsonl")
    hits = phi_hits(log)
    print("\n" + "-" * 64)
    print(f" COMPLIANCE CHECK ({mode.upper()})")
    print("-" * 64)
    print(f" Patient identifiers found in logs : {sum(hits.values())}  {hits if hits else ''}")
    if mode == "naive":
        print(" Human approved the decision       : NO, the agent approved itself")
        print(" Tamper-evident audit trail        : NO, plain text anyone can edit")
    else:
        ok, n = AuditTrail.verify(log)
        print(f" Human approved the decision       : YES, gated on reviewer {reviewer}")
        print(f" Tamper-evident audit trail        : {'YES' if ok else 'BROKEN'}, {n} hash-chained events verified")
    print("-" * 64)


# --------------------------------------------------------------------------- run
PROMPT = (f"Review prior-authorization request {REQUEST['request_id']} for patient {REQUEST['patient_id']}: "
          f"{REQUEST['service']}. Criteria: {REQUEST['criteria']} Fetch the record, decide approve or deny, "
          "and record your decision with a one-sentence rationale.")


async def run(mode: str, reviewer: str) -> None:
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob(f"{mode}_*"):
        f.unlink()
    server = create_sdk_mcp_server("ehr", tools=build_tools(mode))
    base = dict(system_prompt="You are a utilization-management assistant for a health plan.",
                mcp_servers={"ehr": server}, tools=[],  # tools=[]: no shell, no file access
                setting_sources=[],  # ignore ~/.claude/settings.json, which may route to a gateway
                env={"ANTHROPIC_BASE_URL": "https://api.anthropic.com"})

    if mode == "naive":
        options = ClaudeAgentOptions(**base, hooks=naive_hooks(),
                                     allowed_tools=["mcp__ehr__get_patient_record", "mcp__ehr__record_decision"])
    else:
        trail = AuditTrail(OUT / "hardened_audit.jsonl", actor="pa-agent@demo")
        options = ClaudeAgentOptions(**base, hooks=hardened_hooks(trail), strict_mcp_config=True,
                                     allowed_tools=["mcp__ehr__get_patient_record"],  # read-only tool only
                                     can_use_tool=human_approval(trail, reviewer),
                                     max_turns=8, max_budget_usd=1.00)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(PROMPT)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"\nClaude: {block.text}")
            elif isinstance(message, ResultMessage) and message.total_cost_usd is not None:
                print(f"\n(turns: {message.num_turns}, cost: ${message.total_cost_usd:.4f})")
    scorecard(mode, reviewer if mode == "hardened" else None)


if __name__ == "__main__":
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["naive", "hardened"], required=True)
    p.add_argument("--reviewer", default="Dr. J. Rivera (UM nurse reviewer)")
    a = p.parse_args()
    asyncio.run(run(a.mode, a.reviewer))
