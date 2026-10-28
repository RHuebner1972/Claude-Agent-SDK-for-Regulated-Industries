"""
M03-L03: four hooks, one AuditEvent each. No chaining yet (that's M03-L05): just a plain JSONL file.

Hook signature in the Python SDK: async def hook(input_data, tool_use_id, context) -> dict
Return {} to let the call proceed. Returning a deny decision from PreToolUse blocks it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import HookMatcher, ResultMessage

from audit_models import Actor, AgentInfo, AuditEvent


class SimpleAuditLog:
    def __init__(self, path: Path, *, agent: AgentInfo, on_behalf_of: str, correlation_id: str):
        self.path, self.agent, self.on_behalf_of, self.correlation_id = path, agent, on_behalf_of, correlation_id
        self.session_id: str | None = None
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event_type: str, actor: Actor, **fields: Any) -> None:
        event = AuditEvent(event_type=event_type, actor=actor, on_behalf_of=self.on_behalf_of, agent=self.agent,
                           correlation_id=self.correlation_id, session_id=self.session_id, **fields)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json(exclude_none=True) + "\n")

    @property
    def me(self) -> Actor:
        return Actor(kind="agent", id=f"{self.agent.name}@{self.agent.version}")

    # 1. UserPromptSubmit: who asked for what
    async def on_prompt(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.session_id = input_data["session_id"]
        self.write("prompt.submitted", Actor(kind="human", id=self.on_behalf_of), detail={"prompt": input_data["prompt"]})
        return {}

    # 2. PreToolUse: what the agent ASKED to do (before permissions decide)
    async def on_pre_tool(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.write("tool.requested", self.me, tool_name=input_data["tool_name"],
                   tool_use_id=input_data["tool_use_id"], outcome="requested",
                   detail={"input": input_data["tool_input"]})
        return {}

    # 3. PostToolUse: what actually ran and what came back
    async def on_post_tool(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.write("tool.completed", self.me, tool_name=input_data["tool_name"],
                   tool_use_id=input_data["tool_use_id"], outcome="success",
                   detail={"input": input_data["tool_input"], "duration_ms": input_data.get("duration_ms"),
                           "response": str(input_data["tool_response"])[:200]})   # M03-L06 fixes this line
        return {}

    # 4. Stop: the final answer
    async def on_stop(self, input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        self.write("agent.stopped", self.me, detail={"final_answer": input_data.get("last_assistant_message", "")})
        return {}

    # Not a hook: the result message carries denials, turns and cost
    def observe(self, message: Any) -> None:
        if isinstance(message, ResultMessage):
            for d in message.permission_denials or []:
                self.write("tool.denied", Actor(kind="system", id="permission-layer"), tool_name=d["tool_name"],
                           tool_use_id=d["tool_use_id"], outcome="denied", reason="not in allowed_tools")
            self.write("run.completed", Actor(kind="system", id="agent-sdk"),
                       detail={"num_turns": message.num_turns, "total_cost_usd": message.total_cost_usd})

    def sdk_hooks(self) -> dict[str, list[HookMatcher]]:
        return {
            "UserPromptSubmit": [HookMatcher(hooks=[self.on_prompt])],
            "PreToolUse": [HookMatcher(hooks=[self.on_pre_tool])],       # no matcher = every tool
            "PostToolUse": [HookMatcher(hooks=[self.on_post_tool])],
            "Stop": [HookMatcher(hooks=[self.on_stop])],
        }


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
