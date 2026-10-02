"""Dijkstra routing over the physical GMNS network."""

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
        self._outgoing = {}
        for link in instance.links.values():
            self._outgoing.setdefault(link.from_node_id, []).append(link)

    def shortest_path(self, from_yard_id: int, to_yard_id: int) -> Route | None:
        if from_yard_id == to_yard_id:
            return Route((from_yard_id,), (), 0.0)

        heap = [(0.0, from_yard_id)]
        distance = {from_yard_id: 0.0}
        previous = {}

        while heap:
            cost, node = heapq.heappop(heap)
            if cost != distance[node]:
                continue
            if node == to_yard_id:
                break
            for link in self._outgoing.get(node, ()):
                new_cost = cost + link.length
                if new_cost < distance.get(link.to_node_id, float("inf")):
                    distance[link.to_node_id] = new_cost
                    previous[link.to_node_id] = (node, link.link_id)
                    heapq.heappush(heap, (new_cost, link.to_node_id))

        if to_yard_id not in distance:
            return None

        nodes = [to_yard_id]
        links = []
        current = to_yard_id
        while current != from_yard_id:
            parent, link_id = previous[current]
            links.append(link_id)
            nodes.append(parent)
            current = parent
        nodes.reverse()
        links.reverse()
        return Route(tuple(nodes), tuple(links), distance[to_yard_id])
