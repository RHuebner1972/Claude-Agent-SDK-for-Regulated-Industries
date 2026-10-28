# M07-L02: Subagents in the SDK: AgentDefinition, scoped tools and MCP servers

Module: M07 Pillar 6, Multi-Agent Data Boundaries · Type: Code-along

`final/subagents_demo.py` loads the agent cards for Northgate Precision Components' change-board assistant
(synthetic), generates the SDK `AgentDefinition` for the cleared FALCON engineer from its card, shows the
inherit-everything trap (`tools=None`), builds the orchestrator's `ClaudeAgentOptions`, and replays a run so you
can see which agent made each tool call (hook inputs carry `agent_type` inside a subagent).

```bash
uv run python lessons/M07-L02_subagents-in-the-sdk-agentdefinition/final/subagents_demo.py
```
Code walked through on screen: `src/sentinel/boundaries/cards.py`, `policies/agent_cards.yaml`,
`eng_tools.py` (`agent_definition`).

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
