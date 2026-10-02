"""Small executable greedy seed for Phase 3."""

from __future__ import annotations

from .problem import Block, BlockRoute, BlockingSequence, RBPInstance, Solution, default_block_type
from .routing import DijkstraRouter


def build_greedy_solution(instance: RBPInstance, router: DijkstraRouter) -> Solution:
    """Create one direct block per demand.

    This remains a seed, not a claim of equivalence to the competition greedy.
    """
    solution = Solution()
    for demand_id, demand in instance.demands.items():
        block_id = demand_id
        volume = demand.effective_volume(instance.settings)
        solution.blocks[block_id] = Block(
            block_id, demand.origin_yard_id, demand.dest_yard_id,
            default_block_type(demand.commodity_type), volume
        )
        route = router.shortest_path(demand.origin_yard_id, demand.dest_yard_id)
        if route is not None:
            solution.routes[block_id] = BlockRoute(block_id, route.node_ids, route.link_ids)
            solution.sequences[demand_id] = BlockingSequence(demand_id, (block_id,), volume)
    return solution
