"""Prior-authorization review tools, in two versions, plus an offline run driver.

    build_pa_tools(minimized=False)  the naive tool: whole patient record + raw notes go to the model
    build_pa_tools(minimized=True)   minimum necessary: allowlisted fields, age instead of DOB, notes tokenized

simulate_pa_review() drives AuditHooks with the real tool handlers and a scripted "model", so lessons and
tests can compare what reaches the model, the audit log and the final answer, with no API key.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from claude_agent_sdk import ResultMessage, ToolAnnotations, tool
from course_data import patients, prior_auth_criteria, prior_auth_requests

from .detect import known_values
from .mask import mask_text
from .minimize import derive, minimize
from .vault import TOKEN_RE, TokenVault

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
PURPOSE = "prior_auth_review"


class PaRecommendation(BaseModel):
    request_id: str = Field(pattern=r"^PA-\d{4}$")
    recommendation: Literal["approve", "deny", "pend"]
    criterion: int = Field(ge=1, le=8)
    rationale: str = Field(min_length=10)
    policy_rule: str = Field(min_length=3)


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def case_record(request_id: str, *, minimized: bool, vault: TokenVault | None = None) -> dict[str, Any] | None:
    req = next((r for r in prior_auth_requests() if r["request_id"] == request_id), None)
    if req is None:
        return None
    patient = next(p for p in patients() if p["patient_id"] == req["patient_id"])
    if not minimized:
        return {**req, "patient": patient}                       # everything, "so the model has context"
    case = minimize(req, "request", PURPOSE)
    case["patient"] = minimize(derive(patient, req["submitted"]), "patient", PURPOSE)
    strategy = "token" if vault else "redact"
    case["clinical_notes"] = mask_text(req["clinical_notes"], strategy, vault=vault, known=known_values(patient)).text
    return case


def build_pa_tools(*, minimized: bool, vault: TokenVault | None = None, recorded: list[dict] | None = None):
    sink = recorded if recorded is not None else []

    @tool("get_prior_auth_case", "Get one prior-authorization request for review, e.g. PA-2001.",
          {"request_id": str}, annotations=READ_ONLY)
    async def get_prior_auth_case(args: dict[str, Any]) -> dict[str, Any]:
        case = case_record(args["request_id"], minimized=minimized, vault=vault)
        return _text(case) if case else _error(f"No request {args['request_id']!r}.")

    @tool("get_criteria", "Get the payer's medical-necessity criteria.", {}, annotations=READ_ONLY)
    async def get_criteria(args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": prior_auth_criteria()}]}

    @tool("record_pa_recommendation", "Record approve, deny or pend for one request, with the criterion number.",
          PaRecommendation.model_json_schema())
    async def record_pa_recommendation(args: dict[str, Any]) -> dict[str, Any]:
        rec = PaRecommendation.model_validate(args)
        sink.append(rec.model_dump())
        return _text({"recorded": True, "request_id": rec.request_id})

    return [get_prior_auth_case, get_criteria, record_pa_recommendation]


# Scripted reviewer decisions for the offline driver: (recommendation, criterion, clinical reason)
PA_DECISIONS: dict[str, tuple[str, int, str]] = {
    "PA-2001": ("approve", 1, "9 weeks of radicular pain and failed 6 weeks of PT and NSAIDs"),
    "PA-2002": ("approve", 2, "on 4 insulin injections a day with documented hypoglycemia"),
    "PA-2003": ("approve", 3, "active RA after 3 months of methotrexate; TB screening negative"),
    "PA-2004": ("approve", 4, "new headache after age 50 with a focal deficit"),
    "PA-2005": ("approve", 5, "new murmur and no prior echocardiogram"),
    "PA-2006": ("approve", 6, "locking, MRI-confirmed tear and failed 8 weeks of PT"),
    "PA-2007": ("pend", 7, "criterion 7 requires specialist attestation and pharmacist review"),
    "PA-2008": ("pend", 8, "home sleep testing comes first unless comorbidities are documented"),
}


def _patient_ref(case: dict) -> str:
    """What a model would call the patient: the name if it saw one, else the token, else 'the patient'."""
    p = case.get("patient", {})
    if p.get("first_name"):
        return f"{p['first_name']} {p['last_name']} (MRN {p['mrn']})"
    m = TOKEN_RE.search(case.get("clinical_notes", ""))
    return m.group(0) if m else "The patient"


async def simulate_pa_review(hooks, tools, request_ids: list[str] | None = None, *,
                             session_id: str = "sess-pa-51c2") -> list[dict]:
    """Drive the hooks exactly as the SDK would, calling the real tool handlers. Returns the tool responses."""
    by_name = {t.name: t for t in tools}
    base = {"session_id": session_id, "transcript_path": f"~/.claude/projects/pa-review/{session_id}.jsonl",
            "cwd": "/srv/pa-review", "permission_mode": "dontAsk"}
    ids = request_ids or list(PA_DECISIONS)
    seen: list[dict] = []
    counter = iter(range(1, 1000))

    async def call(name: str, args: dict) -> dict:
        tid = f"toolu_{next(counter):03d}"
        full = f"mcp__pa__{name}"
        await hooks.on_pre_tool({**base, "hook_event_name": "PreToolUse", "tool_name": full,
                                 "tool_input": args, "tool_use_id": tid}, tid, {"signal": None})
        result = await by_name[name].handler(args)
        await hooks.on_post_tool({**base, "hook_event_name": "PostToolUse", "tool_name": full, "tool_input": args,
                                  "tool_response": result, "tool_use_id": tid, "duration_ms": 35}, tid, {"signal": None})
        return result

    prompt = "Review the pending prior-authorization requests and record a recommendation for each."
    await hooks.on_prompt({**base, "hook_event_name": "UserPromptSubmit", "prompt": prompt}, None, {"signal": None})
    await call("get_criteria", {})
    summary = []
    for rid in ids:
        result = await call("get_prior_auth_case", {"request_id": rid})
        case = json.loads(result["content"][0]["text"])
        seen.append(case)
        rec, crit, why = PA_DECISIONS[rid]
        ref = _patient_ref(case)
        rationale = f"{ref}: {why}."
        await call("record_pa_recommendation", {"request_id": rid, "recommendation": rec, "criterion": crit,
                                                "rationale": rationale, "policy_rule": f"Criterion {crit}"})
        summary.append(f"{rid} {rec} (criterion {crit}): {rationale}")
    await hooks.on_stop({**base, "hook_event_name": "Stop", "stop_hook_active": False,
                         "last_assistant_message": "Review complete.\n" + "\n".join(summary)}, None, {"signal": None})
    hooks.observe(ResultMessage(subtype="success", duration_ms=51200, duration_api_ms=43010, is_error=False,
                                num_turns=len(ids) * 2 + 2, session_id=session_id, total_cost_usd=0.2114,
                                permission_denials=[], terminal_reason="completed"))
    return seen
