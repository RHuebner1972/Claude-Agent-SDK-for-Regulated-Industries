"""Lab 5 solution: boundary_kit (same design as sentinel.boundaries, which later modules import). agent cards, a boundary guard, typed handoff contracts, routed audit
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
