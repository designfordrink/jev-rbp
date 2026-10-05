"""Exact Drop/Add/Swap evaluation for the clean-room VLNS baseline."""

from __future__ import annotations

from dataclasses import dataclass

from .actions import AddAction, DropAction, SwapAction
from .benchmark import BenchmarkAuthority
from .core import CandidateAction, Evaluation, ValidationResult
from .objective import evaluate_solution
from .problem import Block, BlockType, CommodityType, RBPInstance, Solution
from .rerouting import reroute
from .routing import DijkstraRouter


@dataclass(frozen=True)
class MoveContext:
    instance: RBPInstance
    router: DijkstraRouter


class RBPMoveGenerator:
    """Generate deterministic Drop/Add/Swap candidate pools."""

    def __init__(
        self,
        context: MoveContext,
        *,
        candidate_yards: set[int] | None = None,
    ) -> None:
        self.context = context
        self.candidate_yards = candidate_yards
        self._candidates = self._build_candidates()

    def generate_phase(self, state: Solution, phase: str):
        if phase == "drop":
            return [DropAction(block_id) for block_id in sorted(state.blocks)]

        closed = self._closed_candidates(state)
        if phase == "add":
            return [AddAction(i, j, commodity_type) for i, j, commodity_type in closed]

        if phase == "swap":
            return [
                SwapAction(block_id, i, j, commodity_type)
                for block_id in sorted(state.blocks)
                for i, j, commodity_type in closed
            ]

        raise ValueError(f"unknown move phase: {phase}")

    def _build_candidates(self):
        yards = sorted(
            node.node_id
            for node in self.context.instance.nodes.values()
            if node.node_type == "yard"
            and (
                self.candidate_yards is None
                or node.node_id in self.candidate_yards
            )
        )
        commodity_types = sorted(
            {demand.commodity_type for demand in self.context.instance.demands.values()},
            key=lambda value: value.value,
        )

        candidates = []
        for from_yard in yards:
            for to_yard in yards:
                if from_yard == to_yard:
                    continue
                if self.context.router.shortest_path(from_yard, to_yard) is None:
                    continue
                for commodity_type in commodity_types:
                    candidates.append(
                        (from_yard, to_yard, commodity_type)
                    )
        return tuple(candidates)

    def _closed_candidates(self, state: Solution):
        open_keys = {
            (block.from_yard_id, block.to_yard_id, block.block_type)
            for block in state.blocks.values()
        }
        return tuple(
            candidate
            for candidate in self._candidates
            if (
                candidate[0],
                candidate[1],
                default_block_type(candidate[2]),
            )
            not in open_keys
        )


class RBPMoveApplier:
    """Apply an accepted action and rebuild the complete routed solution."""

    def __init__(self, context: MoveContext) -> None:
        self.context = context

    def apply(self, state: Solution, action: CandidateAction) -> Solution:
        proposed = _virtual_open_blocks(state, action)
        result = reroute(self.context.instance, proposed, self.context.router)
        if result.solution is None:
            raise ValueError(result.reason or "accepted move is unroutable")
        return result.solution


class ExactRBPMoveEvaluator:
    """Authoritative evaluator for RBP local moves."""

    def __init__(self, context: MoveContext) -> None:
        self.context = context

    def evaluate(self, state: Solution, action: CandidateAction) -> Evaluation:
        before = evaluate_solution(self.context.instance, state, self.context.router)
        proposed = _virtual_open_blocks(state, action)
        rerouted = reroute(self.context.instance, proposed, self.context.router)

        if rerouted.solution is None:
            return Evaluation(before.total, float("inf"), False)

        candidate = rerouted.solution
        report = BenchmarkAuthority(self.context.instance).validate(candidate)
        if not report.feasible:
            return Evaluation(before.total, float("inf"), False)

        assert report.cost is not None
        return Evaluation(before.total, report.cost.total, True)


class RBPMoveValidator:
    """Validate search states with the independent benchmark authority."""

    def __init__(self, context: MoveContext) -> None:
        self.context = context

    def validate(self, state: Solution) -> ValidationResult:
        report = BenchmarkAuthority(self.context.instance).validate(state)
        return ValidationResult(report.feasible, tuple(report.violations))


def _virtual_open_blocks(state: Solution, action: CandidateAction) -> dict[int, Block]:
    """Apply a move to the open-block design, without routing it yet."""

    blocks = dict(state.blocks)

    if isinstance(action, DropAction):
        blocks.pop(action.block_id, None)
        return blocks

    next_id = max(blocks, default=0) + 1

    if isinstance(action, AddAction):
        blocks[next_id] = Block(
            next_id,
            action.from_yard_id,
            action.to_yard_id,
            _block_type_for(action.commodity_type),
        )
        return blocks

    if isinstance(action, SwapAction):
        blocks.pop(action.drop_block_id, None)
        blocks[next_id] = Block(
            next_id,
            action.add_from_yard_id,
            action.add_to_yard_id,
            _block_type_for(action.commodity_type),
        )
        return blocks

    raise TypeError(f"unsupported action: {action!r}")


def _minimum_block_volume(instance: RBPInstance, distance: float) -> float:
    settings = instance.settings
    if distance < 100.0:
        return settings.min_block_vol_short
    if distance <= 500.0:
        return settings.min_block_vol_medium
    return settings.min_block_vol_long


def _block_type_for(commodity_type: CommodityType) -> BlockType:
    from .problem import default_block_type

    return default_block_type(commodity_type)


def default_block_type(commodity_type: CommodityType) -> BlockType:
    return _block_type_for(commodity_type)
