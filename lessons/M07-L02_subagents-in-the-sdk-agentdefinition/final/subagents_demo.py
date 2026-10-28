"""
M07-L02: subagents in the SDK. Cards first, then AgentDefinitions generated from them, then who-called-what.

    uv run python lessons/M07-L02_subagents-in-the-sdk-agentdefinition/final/subagents_demo.py
"""
from __future__ import annotations

import asyncio

from claude_agent_sdk import AgentDefinition, ClaudeAgentOptions, create_sdk_mcp_server

from sentinel.boundaries import BoundaryGuard
from sentinel.boundaries.eng_tools import (EngineeringStore, agent_definition, agent_definitions, build_ccb_tools,
                                           build_eng_data_tools, card_set, full_name)
from sentinel.boundaries.simulate import GATED, run_script


def main() -> None:
    cards, version = card_set()
    print(f"1. AGENT CARDS  {cards.name} v{cards.version}  ({version})")
    for c in cards.agents:
        print(f"   {c.name:24} {c.role:12} scope={c.data_scope}  programs={c.programs or 'any'}")
        print(f"   {'':24} tools={c.tools}")
        print(f"   {'':24} delegates to={c.may_delegate_to or '-'}  returns={c.handoff_contract or 'free text'}")

    print("\n2. AGENT DEFINITIONS, generated from the cards")
    for name, d in agent_definitions(cards).items():
        print(f"   {name}: tools={d.tools}")
        print(f"   {'':{len(name)}}  mcpServers={d.mcpServers} maxTurns={d.maxTurns}")
    inherit = AgentDefinition(description="Helpful engineer", prompt="Help with ECRs.")
    print(f"   The trap: AgentDefinition(tools={inherit.tools}) inherits EVERY tool the parent has.")
    bad = cards.get("cleared-engineer-falcon").model_copy(update={"mcp_servers": []})
    try:
        agent_definition(bad)
    except ValueError as exc:
        print(f"   The generator refuses a card that doesn't add up: {exc}")

    store = EngineeringStore()
    ccb, eng = build_ccb_tools(store), build_eng_data_tools(store)
    options = ClaudeAgentOptions(
        system_prompt="You prepare Change Control Board agendas. Delegate FALCON technical review.",
        mcp_servers={"ccb": create_sdk_mcp_server("ccb", tools=ccb),
                     "eng_data": create_sdk_mcp_server("eng_data", tools=eng)},
        tools=["Agent"], allowed_tools=["Agent"] + [full_name(t) for t in cards.get(cards.orchestrator).tools],
        agents=agent_definitions(cards), permission_mode="dontAsk", strict_mcp_config=True, setting_sources=[])
    print(f"\n   Orchestrator options: allowed_tools={options.allowed_tools}")
    print(f"   agents={list(options.agents)}")

    print("\n3. WHO CALLED WHAT: hook inputs carry agent_type inside a subagent, and nothing on the main thread")
    guard = BoundaryGuard(cards, resolver=store.resolve, canaries=store.canaries())
    print(asyncio.run(run_script(ccb + eng, GATED, guard=guard)).table())


if __name__ == "__main__":
    main()
