"""VLNS orchestration boundaries.

The generic solver remains useful for selector experiments. The
ReferenceVLNSSolver below freezes the recovered public-reference control
flow: best Drop, then best Add, and only when neither improves, best Swap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .core import CandidateAction, Evaluation, ValidationResult


class SearchState(Protocol):
    """Marker protocol for a mutable/immutable VLNS search state."""


class MoveGenerator(Protocol):
    def generate(self, state: SearchState) -> Sequence[CandidateAction]: ...


class PhaseMoveGenerator(Protocol):
    """Generate candidates for one reference VLNS move family."""

    def generate_phase(
        self, state: SearchState, phase: str
    ) -> Sequence[CandidateAction]: ...


class MoveEvaluator(Protocol):
    def evaluate(self, state: SearchState, action: CandidateAction) -> Evaluation: ...


class MoveApplier(Protocol):
    def apply(self, state: SearchState, action: CandidateAction) -> SearchState: ...


class StateValidator(Protocol):
    def validate(self, state: SearchState) -> ValidationResult: ...


@dataclass(frozen=True)
class VLNSConfig:
    max_iterations: int = 200
    time_limit_seconds: float | None = 300.0


@dataclass(frozen=True)
class IterationResult:
    iteration: int
    candidates: int
    evaluated: int
    accepted: bool
    best_delta: float | None


@dataclass(frozen=True)
class ReferenceIterationResult:
    """Trace of one reference-shaped VLNS iteration."""

    iteration: int
    drop_evaluated: int
    add_evaluated: int
    swap_evaluated: int
    drop_accepted: bool
    add_accepted: bool
    swap_accepted: bool
    stopped: bool


class VLNSSolver:
    """Generic best-improving orchestration shell."""

    def __init__(
        self,
        generator: MoveGenerator,
        evaluator: MoveEvaluator,
        applier: MoveApplier,
        validator: StateValidator,
        config: VLNSConfig | None = None,
    ) -> None:
        self.generator = generator
        self.evaluator = evaluator
        self.applier = applier
        self.validator = validator
        self.config = config or VLNSConfig()

    def choose_best_improvement(
        self,
        state: SearchState,
        candidates: Sequence[CandidateAction],
    ) -> tuple[CandidateAction, Evaluation] | None:
        return choose_best_improvement(self.evaluator, state, candidates)

    def step(
        self, state: SearchState, iteration: int
    ) -> tuple[SearchState, IterationResult]:
        candidates = list(self.generator.generate(state))
        best = self.choose_best_improvement(state, candidates)

        if best is None:
            return state, IterationResult(
                iteration=iteration,
                candidates=len(candidates),
                evaluated=len(candidates),
                accepted=False,
                best_delta=None,
            )

        action, evaluation = best
        new_state = self.applier.apply(state, action)
        validation = self.validator.validate(new_state)
        if not validation.valid:
            raise ValueError(
                f"accepted move produced invalid state: {validation.violations}"
            )

        return new_state, IterationResult(
            iteration=iteration,
            candidates=len(candidates),
            evaluated=len(candidates),
            accepted=True,
            best_delta=evaluation.delta,
        )


class ReferenceVLNSSolver:
    """Recovered Drop -> Add -> conditional Swap VLNS control flow."""

    def __init__(
        self,
        generator: PhaseMoveGenerator,
        evaluator: MoveEvaluator,
        applier: MoveApplier,
        validator: StateValidator,
        config: VLNSConfig | None = None,
    ) -> None:
        self.generator = generator
        self.evaluator = evaluator
        self.applier = applier
        self.validator = validator
        self.config = config or VLNSConfig()

    def step(
        self, state: SearchState, iteration: int
    ) -> tuple[SearchState, ReferenceIterationResult]:
        drop_evaluated, drop = self._best_phase(state, "drop")
        drop_accepted = drop is not None
        if drop is not None:
            state = self._apply_checked(state, drop)

        add_evaluated, add = self._best_phase(state, "add")
        add_accepted = add is not None
        if add is not None:
            state = self._apply_checked(state, add)

        swap_evaluated = 0
        swap_accepted = False
        if not drop_accepted and not add_accepted:
            swap_evaluated, swap = self._best_phase(state, "swap")
            swap_accepted = swap is not None
            if swap is not None:
                state = self._apply_checked(state, swap)

        stopped = not (drop_accepted or add_accepted or swap_accepted)
        return state, ReferenceIterationResult(
            iteration=iteration,
            drop_evaluated=drop_evaluated,
            add_evaluated=add_evaluated,
            swap_evaluated=swap_evaluated,
            drop_accepted=drop_accepted,
            add_accepted=add_accepted,
            swap_accepted=swap_accepted,
            stopped=stopped,
        )

    def solve(
        self, state: SearchState
    ) -> tuple[SearchState, tuple[ReferenceIterationResult, ...]]:
        results: list[ReferenceIterationResult] = []
        for iteration in range(self.config.max_iterations):
            state, result = self.step(state, iteration)
            results.append(result)
            if result.stopped:
                break
        return state, tuple(results)

    def _best_phase(
        self, state: SearchState, phase: str
    ) -> tuple[int, tuple[CandidateAction, Evaluation] | None]:
        candidates = list(self.generator.generate_phase(state, phase))
        return len(candidates), choose_best_improvement(
            self.evaluator, state, candidates
        )

    def _apply_checked(
        self,
        state: SearchState,
        best: tuple[CandidateAction, Evaluation],
    ) -> SearchState:
        action, _ = best
        new_state = self.applier.apply(state, action)
        validation = self.validator.validate(new_state)
        if not validation.valid:
            raise ValueError(
                f"accepted move produced invalid state: {validation.violations}"
            )
        return new_state


def choose_best_improvement(
    evaluator: MoveEvaluator,
    state: SearchState,
    candidates: Sequence[CandidateAction],
) -> tuple[CandidateAction, Evaluation] | None:
    """Evaluate all candidates and return the strictly improving best move."""

    best: tuple[CandidateAction, Evaluation] | None = None
    for action in candidates:
        evaluation = evaluator.evaluate(state, action)
        if not evaluation.feasible or evaluation.delta >= 0:
            continue
        if best is None or evaluation.delta < best[1].delta:
            best = (action, evaluation)
    return best
