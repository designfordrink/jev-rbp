"""Routing service boundary for RBP exact evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Route:
    """A physical path through the rail network."""

    node_ids: tuple[int, ...]
    link_ids: tuple[int, ...]
    distance: float


class RoutingEngine(Protocol):
    """Authoritative shortest/feasible routing service."""

    def shortest_path(self, from_yard_id: int, to_yard_id: int) -> Route | None: ...

    def route_block(self, from_yard_id: int, to_yard_id: int) -> Route | None: ...
