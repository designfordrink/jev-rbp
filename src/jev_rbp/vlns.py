"""VLNS orchestration boundary.

This module intentionally contains only the search-loop contract in v0.1.
Problem-specific move generation, routing, exact evaluation and validation
will be implemented behind these interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Protocol

from .core import CandidateAction, Evaluation, ValidationResult


class SearchState(Protocol):
    """Marker protocol for a mutable/immutable VLNS search state."""


class MoveGenerator(Protocol):
    def generate(self, state: SearchState) -> Sequence[CandidateAction]: ...


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


class VLNSSolver:
    """Reference-shaped best-improving orchestration shell.

    The solver is deliberately not connected to the real RBP implementation yet.
    Its purpose is to freeze the Phase-2 control-flow boundary before Phase 3.
    """

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
        best: tuple[CandidateAction, Evaluation] | None = None

        for action in candidates:
            evaluation = self.evaluator.evaluate(state, action)
            if not evaluation.feasible:
                continue
            if evaluation.delta >= 0:
                continue
            if best is None or evaluation.delta < best[1].delta:
                best = (action, evaluation)

        return best

    def step(self, state: SearchState, iteration: int) -> tuple[SearchState, IterationResult]:
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
