"""Directed blocking-service graph and commodity routing.

Physical rail links are handled by DijkstraRouter. This module builds the
separate directed graph of opened blocks used by the VLNS reference logic.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Iterable

from .problem import Block, CommodityType, RBPInstance
from .routing import DijkstraRouter


@dataclass(frozen=True)
class ServiceRoute:
    """A commodity route through opened directed blocks."""

    block_ids: tuple[int, ...]
    cost_per_car: float


class BlockServiceRouter:
    """Route commodities through the directed block-service graph.

    An arc is a block. Its per-car cost is transport cost for the block's
    physical shortest path plus handling cost at the receiving yard when that
    yard is an intermediate point rather than the commodity destination.
    """

    def __init__(self, instance: RBPInstance, physical_router: DijkstraRouter) -> None:
        self.instance = instance
        self.physical_router = physical_router
        self._physical_routes = {}

    def physical_route(self, block: Block):
        route = self._physical_routes.get(block.block_id)
        if route is None:
            route = self.physical_router.shortest_path(
                block.from_yard_id, block.to_yard_id
            )
            self._physical_routes[block.block_id] = route
        return route

    def route(
        self,
        origin_yard_id: int,
        dest_yard_id: int,
        commodity_type: CommodityType,
        blocks: Iterable[Block],
    ) -> ServiceRoute | None:
        usable = {
            block.block_id: block
            for block in blocks
            if block.block_type == _block_type_for(commodity_type)
            and block.from_yard_id != block.to_yard_id
            and self.physical_route(block) is not None
        }
        if origin_yard_id == dest_yard_id:
            return ServiceRoute((), 0.0)
        if not usable:
            return None

        outgoing: dict[int, list[Block]] = {}
        for block in usable.values():
            outgoing.setdefault(block.from_yard_id, []).append(block)

        distances = {origin_yard_id: 0.0}
        previous: dict[int, tuple[int, int]] = {}
        heap = [(0.0, origin_yard_id)]

        while heap:
            cost, yard = heapq.heappop(heap)
            if cost != distances.get(yard):
                continue
            if yard == dest_yard_id:
                break

            for block in outgoing.get(yard, ()):
                physical = self.physical_route(block)
                assert physical is not None
                handling = (
                    self.instance.nodes[block.to_yard_id].handling_cost
                    if block.to_yard_id != dest_yard_id
                    else 0.0
                )
                arc_cost = (
                    physical.distance * self.instance.settings.transport_cost_coefficient
                    + handling
                )
                new_cost = cost + arc_cost
                if new_cost < distances.get(block.to_yard_id, float("inf")):
                    distances[block.to_yard_id] = new_cost
                    previous[block.to_yard_id] = (yard, block.block_id)
                    heapq.heappush(heap, (new_cost, block.to_yard_id))

        if dest_yard_id not in distances:
            return None

        block_ids: list[int] = []
        current = dest_yard_id
        while current != origin_yard_id:
            parent, block_id = previous[current]
            block_ids.append(block_id)
            current = parent
        block_ids.reverse()
        return ServiceRoute(tuple(block_ids), distances[dest_yard_id])


def _block_type_for(commodity_type: CommodityType):
    from .problem import default_block_type

    return default_block_type(commodity_type)
