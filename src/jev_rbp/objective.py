"""Benchmark-aligned operating-cost evaluation for a complete RBP solution."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .problem import RBPInstance, Solution
from .routing import DijkstraRouter


CLASS_I_RAILROADS = frozenset({"BNSF", "CN", "CSX", "UP", "NS", "CPKC"})


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
    """Evaluate operating cost using the released benchmark cost formula.

    Block volumes are derived from blocking sequences, matching the benchmark's
    actual-volume semantics. Physical block routes are used when present;
    otherwise the shortest physical route is used.
    """

    actual_volumes = _actual_block_volumes(solution)
    fixed = len(solution.blocks) * instance.settings.block_fixed_cost
    transport = 0.0
    handling = 0.0

    for block_id, block in solution.blocks.items():
        volume = actual_volumes.get(block_id, 0.0)
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
            volume
            * distance
            * instance.settings.transport_cost_coefficient
        )

    for sequence in solution.sequences.values():
        for block_id in sequence.block_ids[:-1]:
            block = solution.blocks.get(block_id)
            if block is not None:
                handling += (
                    sequence.volume
                    * instance.nodes[block.to_yard_id].handling_cost
                )

    interchange = 0.0
    for block_id, volume in actual_volumes.items():
        if volume <= 0:
            continue
        block = solution.blocks.get(block_id)
        if block is None:
            continue
        origin_rr = _class_i_railroad(
            instance.nodes[block.from_yard_id].railroad_id
        )
        dest_rr = _class_i_railroad(
            instance.nodes[block.to_yard_id].railroad_id
        )
        if origin_rr and dest_rr and origin_rr != dest_rr:
            interchange += volume * instance.settings.interchange_cost

    return Objective(
        fixed_block=fixed,
        transport=transport,
        handling=handling,
        interchange=interchange,
    )


def evaluate_direct_solution(
    instance: RBPInstance, solution: Solution, router: DijkstraRouter
) -> Objective:
    """Backward-compatible alias for the initial objective API."""

    return evaluate_solution(instance, solution, router)


def _actual_block_volumes(solution: Solution) -> dict[int, float]:
    volumes: dict[int, float] = defaultdict(float)
    for sequence in solution.sequences.values():
        for block_id in sequence.block_ids:
            volumes[block_id] += sequence.volume
    return dict(volumes)


def _class_i_railroad(railroad_id: str) -> str | None:
    normalized = railroad_id.strip().upper()
    if normalized == "CSXT":
        normalized = "CSX"
    return normalized if normalized in CLASS_I_RAILROADS else None
