"""Selector-aware VLNS used for controlled baseline experiments."""

from __future__ import annotations

from dataclasses import dataclass

from .core import CandidateAction, Evaluation, Selector, ValidationResult
from .trace import PhaseTrace, SearchTrace
from .vlns import (
    MoveApplier,
    MoveEvaluator,
    PhaseMoveGenerator,
    SearchState,
    StateValidator,
    choose_best_improvement,
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
    """Reference-shaped VLNS whose expensive evaluations are selector-controlled.

    Candidate generation, exact evaluation, validation, and phase order remain
    unchanged. The selector only determines which candidates receive an exact
    evaluation, subject to the fixed per-phase budget.
    """

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

    def solve(
        self, state: SearchState
    ) -> tuple[SearchState, tuple[SelectorIterationResult, ...]]:
        results: list[SelectorIterationResult] = []
        for iteration in range(self.config.max_iterations):
            state, result, stopped = self._step(state, iteration)
            results.append(result)
            if stopped:
                break
        return state, tuple(results)

    def solve_with_trace(
        self, state: SearchState
    ) -> tuple[SearchState, SearchTrace]:
        phases: list[PhaseTrace] = []
        for iteration in range(self.config.max_iterations):
            state, _, drop_trace, drop_accepted = self._run_phase(
                state, iteration, "drop"
            )
            phases.append(drop_trace)

            state, _, add_trace, add_accepted = self._run_phase(
                state, iteration, "add"
            )
            phases.append(add_trace)

            swap_accepted = False
            if not drop_accepted and not add_accepted:
                state, swap, swap_trace, swap_accepted = self._run_phase(
                    state, iteration, "swap"
                )
                phases.append(swap_trace)

            if not (drop_accepted or add_accepted or swap_accepted):
                break

        return state, SearchTrace(tuple(phases))

    def _step(
        self, state: SearchState, iteration: int
    ) -> tuple[SearchState, SelectorIterationResult, bool]:
        state, _, drop_trace, drop_accepted = self._run_phase(
            state, iteration, "drop"
        )
        state, _, add_trace, add_accepted = self._run_phase(
            state, iteration, "add"
        )

        swap_trace = None
        swap_accepted = False
        if not drop_accepted and not add_accepted:
            state, _, swap_trace, swap_accepted = self._run_phase(
                state, iteration, "swap"
            )

        result = SelectorIterationResult(
            iteration=iteration,
            drop_candidates=drop_trace.candidates,
            add_candidates=add_trace.candidates,
            swap_candidates=0 if swap_trace is None else swap_trace.candidates,
            drop_evaluated=drop_trace.evaluated,
            add_evaluated=add_trace.evaluated,
            swap_evaluated=0 if swap_trace is None else swap_trace.evaluated,
            accepted=drop_accepted or add_accepted or swap_accepted,
        )
        return state, result, not result.accepted

    def _run_phase(
        self, state: SearchState, iteration: int, phase: str
    ) -> tuple[
        SearchState,
        tuple[CandidateAction, Evaluation] | None,
        PhaseTrace,
        bool,
    ]:
        candidates = list(self.generator.generate_phase(state, phase))
        ranked = list(self.selector.rank(state, candidates))
        budget = self.config.exact_evaluations_per_phase
        if budget < 0:
            raise ValueError("exact_evaluations_per_phase must be non-negative")
        selected = ranked if budget is None else ranked[:budget]
        best = choose_best_improvement(self.evaluator, state, selected)
        accepted = best is not None
        if best is not None:
            state = self._apply_checked(state, best)

        trace = PhaseTrace(
            iteration=iteration,
            phase=phase,
            candidates=len(candidates),
            evaluated=len(selected),
            accepted=accepted,
            best_delta=None if best is None else best[1].delta,
        )
        return state, best, trace, accepted

    def _apply_checked(
        self,
        state: SearchState,
        best: tuple[CandidateAction, Evaluation],
    ) -> SearchState:
        new_state = self.applier.apply(state, best[0])
        validation = self.validator.validate(new_state)
        if not validation.valid:
            raise ValueError(
                f"accepted move produced invalid state: {validation.violations}"
            )
        return new_state
