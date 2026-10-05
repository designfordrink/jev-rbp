"""Selector-aware VLNS used for controlled baseline experiments."""

from __future__ import annotations

from dataclasses import dataclass

from .core import Selector
from .trace import PhaseTrace, SearchTrace
from .vlns import (
    run_vlns,
    MoveApplier,
    MoveEvaluator,
    PhaseMoveGenerator,
    SearchState,
    StateValidator,
)


@dataclass(frozen=True)
class SelectorVLNSConfig:
    """Configuration for a selector-controlled VLNS experiment."""

    max_iterations: int = 200
    exact_evaluations_per_phase: int | None = 1
    time_limit_seconds: float | None = 300.0


@dataclass(frozen=True)
class SelectorIterationResult:
    """Metrics for one selector-controlled VLNS iteration."""

    iteration: int
    drop_candidates: int
    add_candidates: int
    swap_candidates: int
    drop_evaluated: int
    add_evaluated: int
    swap_evaluated: int
    accepted: bool


class SelectorVLNSSolver:
    """Compatibility wrapper around the canonical VLNS engine."""

    def __init__(
        self,
        generator: PhaseMoveGenerator,
        selector: Selector,
        evaluator: MoveEvaluator,
        applier: MoveApplier,
        validator: StateValidator,
        config: SelectorVLNSConfig | None = None,
    ) -> None:
        self.generator = generator
        self.selector = selector
        self.evaluator = evaluator
        self.applier = applier
        self.validator = validator
        self.config = config or SelectorVLNSConfig()

    def solve(self, state: SearchState) -> tuple[SearchState, tuple[SelectorIterationResult, ...]]:
        result = run_vlns(
            state,
            self.generator,
            self.evaluator,
            self.applier,
            self.validator,
            selector=self.selector,
            exact_evaluations_per_phase=self.config.exact_evaluations_per_phase,
            max_iterations=self.config.max_iterations,
        )
        return result.state, _iteration_results(result.trace)

    def solve_with_trace(
        self, state: SearchState
    ) -> tuple[SearchState, SearchTrace]:
        result = run_vlns(
            state,
            self.generator,
            self.evaluator,
            self.applier,
            self.validator,
            selector=self.selector,
            exact_evaluations_per_phase=self.config.exact_evaluations_per_phase,
            max_iterations=self.config.max_iterations,
        )
        return result.state, result.trace


def _iteration_results(trace: SearchTrace) -> tuple[SelectorIterationResult, ...]:
    by_iteration: dict[int, list[PhaseTrace]] = {}
    for phase in trace.phases:
        by_iteration.setdefault(phase.iteration, []).append(phase)

    results: list[SelectorIterationResult] = []
    for iteration, phases in sorted(by_iteration.items()):
        lookup = {phase.phase: phase for phase in phases}
        drop = lookup["drop"]
        add = lookup["add"]
        swap = lookup.get("swap")
        results.append(
            SelectorIterationResult(
                iteration=iteration,
                drop_candidates=drop.candidates,
                add_candidates=add.candidates,
                swap_candidates=0 if swap is None else swap.candidates,
                drop_evaluated=drop.evaluated,
                add_evaluated=add.evaluated,
                swap_evaluated=0 if swap is None else swap.evaluated,
                accepted=(
                    drop.accepted
                    or add.accepted
                    or (swap.accepted if swap is not None else False)
                ),
            )
        )
    return tuple(results)
