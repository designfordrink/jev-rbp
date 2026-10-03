"""RBP-specific cheap selector heuristics."""

from __future__ import annotations

from .actions import AddAction, DropAction, SwapAction
from .core import CandidateAction
from .problem import RBPInstance, Solution
from .routing import DijkstraRouter
from .selectors import GreedySelector


class RBPGreedySelector(GreedySelector):
    """Cheap cost-proxy selector for RBP Drop/Add/Swap candidates.

    The proxy estimates the physical cost of opening an added block and the
    cost avoided by dropping a currently used block. It deliberately ignores
    rerouting interactions, so the exact evaluator remains authoritative.
    """

    def __init__(self, instance: RBPInstance, router: DijkstraRouter) -> None:
        self.instance = instance
        self.router = router
        super().__init__(self._score)

    def _score(self, state: object, action: CandidateAction) -> float:
        if not isinstance(state, Solution):
            raise TypeError("RBPGreedySelector expects a Solution state")

        if isinstance(action, DropAction):
            block = state.blocks.get(action.block_id)
            if block is None:
                return float("inf")
            distance = self._distance(block.from_yard_id, block.to_yard_id)
            return -self._block_cost(block.volume, distance)

        if isinstance(action, AddAction):
            distance = self._distance(action.from_yard_id, action.to_yard_id)
            return self._block_cost(
                self._minimum_volume(distance),
                distance,
            )

        if isinstance(action, SwapAction):
            block = state.blocks.get(action.drop_block_id)
            if block is None:
                return float("inf")
            add_distance = self._distance(
                action.add_from_yard_id,
                action.add_to_yard_id,
            )
            drop_distance = self._distance(block.from_yard_id, block.to_yard_id)
            return (
                self._block_cost(self._minimum_volume(add_distance), add_distance)
                - self._block_cost(block.volume, drop_distance)
            )

        raise TypeError(f"unsupported action: {action!r}")

    def _distance(self, from_yard_id: int, to_yard_id: int) -> float:
        route = self.router.shortest_path(from_yard_id, to_yard_id)
        return float("inf") if route is None else route.distance

    def _minimum_volume(self, distance: float) -> float:
        settings = self.instance.settings
        if distance < 100.0:
            return settings.min_block_vol_short
        if distance <= 500.0:
            return settings.min_block_vol_medium
        return settings.min_block_vol_long

    def _block_cost(self, volume: float, distance: float) -> float:
        settings = self.instance.settings
        return (
            settings.block_fixed_cost
            + volume * distance * settings.transport_cost_coefficient
        )
