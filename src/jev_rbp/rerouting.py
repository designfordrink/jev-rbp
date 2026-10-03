"""Reroute all demands through a proposed directed block design."""

from __future__ import annotations

from dataclasses import dataclass

from .problem import Block, BlockRoute, BlockingSequence, RBPInstance, Solution
from .routing import DijkstraRouter
from .service import BlockServiceRouter


@dataclass(frozen=True)
class RerouteResult:
    solution: Solution | None
    reason: str | None = None


def reroute(
    instance: RBPInstance,
    open_blocks: dict[int, Block],
    physical_router: DijkstraRouter,
) -> RerouteResult:
    """Build a complete solution by routing every demand on open blocks.

    A candidate is rejected here if any demand becomes unroutable. Volumes are
    then aggregated over used blocks. Unused opened blocks are removed, matching
    the reference solver's distinction between candidate blocks and actually
    used blocks.
    """

    service = BlockServiceRouter(instance, physical_router)
    sequences: dict[int, BlockingSequence] = {}

    for demand_id, demand in instance.demands.items():
        route = service.route(
            demand.origin_yard_id,
            demand.dest_yard_id,
            demand.commodity_type,
            open_blocks.values(),
        )
        if route is None:
            return RerouteResult(None, f"demand {demand_id} is unroutable")

        sequences[demand_id] = BlockingSequence(
            demand_id=demand_id,
            block_ids=route.block_ids,
            volume=demand.effective_volume(instance.settings),
        )

    volumes: dict[int, float] = {}
    for sequence in sequences.values():
        for block_id in sequence.block_ids:
            volumes[block_id] = volumes.get(block_id, 0.0) + sequence.volume

    used_blocks = {
        block_id: Block(
            block.block_id,
            block.from_yard_id,
            block.to_yard_id,
            block.block_type,
            volumes[block_id],
        )
        for block_id, block in open_blocks.items()
        if block_id in volumes
    }

    routes = {}
    for block_id, block in used_blocks.items():
        physical = service.physical_route(block)
        if physical is None:
            return RerouteResult(None, f"block {block_id} has no physical route")
        routes[block_id] = BlockRoute(
            block_id=block_id,
            node_ids=physical.node_ids,
            link_ids=physical.link_ids,
        )

    return RerouteResult(
        Solution(blocks=used_blocks, sequences=sequences, routes=routes)
    )
