"""Offline tests for Module 5 code (no API key needed). Run: uv run pytest tests/test_m05_offline.py"""
import asyncio
import importlib.util
import sys
from pathlib import Path

from claude_agent_sdk import HookMatcher

from sentinel.policy import PolicyEngine, Subject, build_context, merge_hooks, permission_flow
from sentinel.policy.complaint_tools import COMPLAINTS_POLICY, ComplaintStore, build_complaint_tools, complaint_enforcer
from sentinel.policy.simulate import INJECTED_TRIAGE, run_script

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
LAB = REPO / "labs" / "lab3_policy-engine"


def load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(path.parent))


def test_lab_solution_matches_the_toolkit():
    for name in ("models.py", "engine.py", "enforce.py", "complaint_tools.py", "permissions.py", "simulate.py",
                 "policies/complaints.yaml"):
        assert (LAB / "solution/policy_gate" / name).read_text() == (REPO / "src/sentinel/policy" / name).read_text(), name


def test_permission_flow_follows_the_documented_order():
    C = "mcp__complaints__"
    assert permission_flow("Bash", mode="bypassPermissions").decision == "allow"
    assert permission_flow("Bash", mode="bypassPermissions", disallowed_tools=["Bash"]).stage.startswith("2")
    assert permission_flow(C + "close_complaint", mode="bypassPermissions",
                           hook=lambda t: "deny").stage.startswith("1")
    assert permission_flow(C + "close_complaint", mode="dontAsk", allowed_tools=[C + "get_complaint"]).decision == "deny"
    assert permission_flow(C + "get_complaint", mode="dontAsk", allowed_tools=[C + "get_complaint"]).decision == "allow"
    assert permission_flow(C + "x", mode="default", can_use_tool=lambda t: True).stage.startswith("6")


def test_l02_regulated_config_denies_shell_and_unlisted_writes(capsys):
    load(LESSONS / "M05-L02_the-sdk-permission-stack-allowed/final/permission_stack.py", "m05_perm").main()
    out = capsys.readouterr().out
    assert "DENY  at 2 deny rule (disallowed_tools)" in out and "DENY  at 1 PreToolUse hook" in out


def test_l04_policy_demo(capsys):
    load(LESSONS / "M05-L04_building-a-policy-engine-with-pydantic/final/policy_demo.py", "m05_policy").main()
    out = capsys.readouterr().out
    assert "MDR-002" in out and "MDR-001" in out and "DEFAULT-DENY" in out and "rejected with 3 errors" in out


def test_l05_abac_matrix(capsys):
    load(LESSONS / "M05-L05_context-aware-decisions-role-data-class/final/abac_demo.py", "m05_abac").main()
    out = capsys.readouterr().out
    assert "allow MDR-010" in out and "PUR-001" in out and out.count("COM-001") == 3


def test_l06_and_l07_demos_run(capsys):
    asyncio.run(load(LESSONS / "M05-L06_pre-and-post-conditions-validating-tool/final/conditions_demo.py",
                     "m05_cond").main())
    asyncio.run(load(LESSONS / "M05-L07_prompt-injection-as-a-policy-problem/final/injection_demo.py",
                     "m05_inj").main())
    out = capsys.readouterr().out
    assert "PRE-001" in out and "POST-001" in out and "INJ-003" in out and "approver says yes  -> EXECUTED" in out


def test_naive_run_is_compromised_and_gated_run_is_not():
    store = ComplaintStore()
    asyncio.run(run_script(build_complaint_tools(store), INJECTED_TRIAGE, mode="bypassPermissions"))
    assert store.records["CMP-3006"]["status"] == "closed" and store.outbox
    store = ComplaintStore()
    enforcer = complaint_enforcer(store, Subject(user="a", role="regulatory_affairs", purpose="complaint_handling"))
    asyncio.run(run_script(build_complaint_tools(store), INJECTED_TRIAGE, enforcer=enforcer))
    assert store.records["CMP-3006"]["status"] == "open" and not store.outbox


def test_every_decision_names_the_exact_policy_version():
    engine = PolicyEngine.from_file(COMPLAINTS_POLICY)
    d = engine.evaluate(build_context(Subject(user="a", role="qa_specialist", purpose="complaint_handling"),
                                      "close_complaint", {"complaint_id": "CMP-3003"},
                                      ComplaintStore().resolve("close_complaint", {"complaint_id": "CMP-3003"}),
                                      {"tainted": False}))
    assert d.policy_version == engine.version and d.message().startswith("[MDR-001]")


def test_merge_hooks_runs_in_order_and_stops_at_first_deny():
    calls = []

    def hook(name, deny=False):
        async def cb(input_data, tool_use_id, context):
            calls.append(name)
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": name}} if deny else {}
        return cb
    merged = merge_hooks({"PreToolUse": [HookMatcher(hooks=[hook("audit")])]},
                         {"PreToolUse": [HookMatcher(hooks=[hook("policy", deny=True)])]},
                         {"PreToolUse": [HookMatcher(hooks=[hook("never")])]})
    assert len(merged["PreToolUse"]) == 1
    out = asyncio.run(merged["PreToolUse"][0].hooks[0]({"tool_name": "x"}, "t1", None))
    assert calls == ["audit", "policy"] and out["hookSpecificOutput"]["permissionDecisionReason"] == "policy"
