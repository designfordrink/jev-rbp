"""Small executable greedy seed for Phase 3."""

from __future__ import annotations

from .problem import Block, BlockRoute, BlockingSequence, RBPInstance, Solution
from .routing import DijkstraRouter


def build_greedy_solution(instance: RBPInstance, router: DijkstraRouter) -> Solution:
    """Create one direct block per demand.

    This is a seed implementation, not claimed equivalent to the Kaggle greedy heuristic.
    """
    solution = Solution()
    for demand_id, demand in instance.demands.items():
        block_id = demand_id
        volume = demand.volume * instance.settings.demand_multiplier
        solution.blocks[block_id] = Block(
            block_id, demand.origin_yard_id, demand.dest_yard_id,
            demand.commodity_type, volume
        )
        route = router.shortest_path(demand.origin_yard_id, demand.dest_yard_id)
        if route is not None:
            solution.routes[block_id] = BlockRoute(block_id, route.node_ids, route.link_ids)
            solution.sequences[demand_id] = BlockingSequence(demand_id, (block_id,), volume)
    return solution
