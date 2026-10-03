"""Reference-shaped objective evaluation for a complete RBP solution."""

from __future__ import annotations

from dataclasses import dataclass

from .problem import RBPInstance, Solution
from .routing import DijkstraRouter


@dataclass(frozen=True)
class Objective:
    fixed_block: float
    transport: float
    handling: float = 0.0
    interchange: float = 0.0

    @property
    def total(self) -> float:
        return self.fixed_block + self.transport + self.handling + self.interchange


def evaluate_solution(
    instance: RBPInstance,
    solution: Solution,
    router: DijkstraRouter,
) -> Objective:
    """Evaluate the reference move objective on a complete solution."""

    fixed = len(solution.blocks) * instance.settings.block_fixed_cost
    transport = 0.0
    handling = 0.0

    for block_id, block in solution.blocks.items():
        route = solution.routes.get(block_id)
        if route is None:
            physical = router.shortest_path(block.from_yard_id, block.to_yard_id)
            distance = physical.distance if physical is not None else float("inf")
        else:
            distance = sum(
                instance.links[link_id].length
                for link_id in route.link_ids
                if link_id in instance.links
            )
        transport += (
            block.volume
            * distance
            * instance.settings.transport_cost_coefficient
        )

    for sequence in solution.sequences.values():
        if len(sequence.block_ids) <= 1:
            continue
        for block_id in sequence.block_ids[:-1]:
            block = solution.blocks.get(block_id)
            if block is None:
                continue
            handling += sequence.volume * instance.nodes[block.to_yard_id].handling_cost

    return Objective(
        fixed_block=fixed,
        transport=transport,
        handling=handling,
        interchange=0.0,
    )


def evaluate_direct_solution(
    instance: RBPInstance, solution: Solution, router: DijkstraRouter
) -> Objective:
    """Backward-compatible alias for the initial objective API."""

    return evaluate_solution(instance, solution, router)
