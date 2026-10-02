"""Objective components for the first executable baseline."""

from __future__ import annotations

from dataclasses import dataclass

from .problem import RBPInstance, Solution
from .routing import DijkstraRouter


@dataclass(frozen=True)
class Objective:
    fixed_block: float
    transport: float

    @property
    def total(self) -> float:
        return self.fixed_block + self.transport


def evaluate_direct_solution(
    instance: RBPInstance, solution: Solution, router: DijkstraRouter
) -> Objective:
    fixed = len(solution.blocks) * instance.settings.block_fixed_cost
    transport = 0.0
    for demand in instance.demands.values():
        route = router.shortest_path(demand.origin_yard_id, demand.dest_yard_id)
        if route is not None:
            transport += (
                demand.volume * instance.settings.demand_multiplier
                * route.distance * instance.settings.transport_cost_coefficient
            )
    return Objective(fixed_block=fixed, transport=transport)
