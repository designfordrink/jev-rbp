"""Dijkstra routing over the physical GMNS network.

The RAS reference treats physical links as bidirectional. The service/block
graph is directed and is built separately by the VLNS evaluator.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Protocol

from .problem import RBPInstance


@dataclass(frozen=True)
class Route:
    node_ids: tuple[int, ...]
    link_ids: tuple[int, ...]
    distance: float


class RoutingEngine(Protocol):
    def shortest_path(self, from_yard_id: int, to_yard_id: int) -> Route | None: ...


class DijkstraRouter:
    def __init__(self, instance: RBPInstance) -> None:
        self.instance = instance
        # Physical links are bidirectional for shortest-path purposes.
        # Keep the original link_id when traversing a record in either direction.
        self._adjacency: dict[int, list[tuple[int, float, int]]] = {}
        for link in instance.links.values():
            self._adjacency.setdefault(link.from_node_id, []).append(
                (link.to_node_id, link.length, link.link_id)
            )
            self._adjacency.setdefault(link.to_node_id, []).append(
                (link.from_node_id, link.length, link.link_id)
            )

    def shortest_path(self, from_yard_id: int, to_yard_id: int) -> Route | None:
        if from_yard_id == to_yard_id:
            return Route((from_yard_id,), (), 0.0)

        heap = [(0.0, from_yard_id)]
        distance = {from_yard_id: 0.0}
        previous: dict[int, tuple[int, int]] = {}

        while heap:
            cost, node = heapq.heappop(heap)
            if cost != distance[node]:
                continue
            if node == to_yard_id:
                break

            for neighbor, length, link_id in self._adjacency.get(node, ()):
                new_cost = cost + length
                if new_cost < distance.get(neighbor, float("inf")):
                    distance[neighbor] = new_cost
                    previous[neighbor] = (node, link_id)
                    heapq.heappush(heap, (new_cost, neighbor))

        if to_yard_id not in distance:
            return None

        nodes = [to_yard_id]
        links: list[int] = []
        current = to_yard_id
        while current != from_yard_id:
            parent, link_id = previous[current]
            links.append(link_id)
            nodes.append(parent)
            current = parent

        nodes.reverse()
        links.reverse()
        return Route(tuple(nodes), tuple(links), distance[to_yard_id])
