"""Lab 5 starter: boundary_kit. Part 1: TODO 1 residency.py, TODOs 2-3 guard.py, TODO 4 routing.py.
Part 2: TODO 5 markings.py, TODO 6 contracts.py, TODO 7 guard.py, TODO 8 ../boundary_pipeline.py.
boundary_kit (same design as sentinel.boundaries, which later modules import). agent cards, a boundary guard, typed handoff contracts, routed audit
logs and residency checks.

    cards, _ = card_set()
    guard  = BoundaryGuard(cards, resolver=store.resolve, canaries=store.canaries(), audit=routed)
    hooks  = merge_hooks(routed.sdk_hooks(), guard.sdk_hooks())
    options = ClaudeAgentOptions(..., agents=agent_definitions(cards), hooks=hooks)
"""
from .cards import AgentCard, CardSet, Deployment, load_cards
from .contracts import CONTRACTS, ChangeImpactSummary, HandoffResult, enforce_contract
from .guard import BoundaryGuard
from .markings import canaries_from, scan
from .residency import check_all, check_deployment
from .routing import RoutingAuditHooks

__all__ = ["AgentCard", "BoundaryGuard", "CONTRACTS", "CardSet", "ChangeImpactSummary", "Deployment", "HandoffResult",
           "RoutingAuditHooks", "canaries_from", "check_all", "check_deployment", "enforce_contract", "load_cards",
           "scan"]
