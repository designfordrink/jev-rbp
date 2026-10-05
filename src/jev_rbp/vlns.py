"""VLNS orchestration boundaries.

The generic solver remains useful for selector experiments. The
ReferenceVLNSSolver below freezes the recovered public-reference control
flow: best Drop, then best Add, and only when neither improves, best Swap.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .core import CandidateAction, Evaluation, Selector, ValidationResult
from .trace import PhaseTrace, SearchTrace


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
    """Compatibility wrapper for canonical Vanilla VLNS control flow."""

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
        result = run_vlns(
            state,
            self.generator,
            self.evaluator,
            self.applier,
            self.validator,
            max_iterations=1,
        )
        phases = [p for p in result.trace.phases if p.iteration == 0]
        lookup = {p.phase: p for p in phases}
        drop = lookup["drop"]
        add = lookup["add"]
        swap = lookup.get("swap")
        return result.state, ReferenceIterationResult(
            iteration=iteration,
            drop_evaluated=drop.evaluated,
            add_evaluated=add.evaluated,
            swap_evaluated=0 if swap is None else swap.evaluated,
            drop_accepted=drop.accepted,
            add_accepted=add.accepted,
            swap_accepted=False if swap is None else swap.accepted,
            stopped=not result.accepted_moves,
        )

    def solve(
        self, state: SearchState
    ) -> tuple[SearchState, tuple[ReferenceIterationResult, ...]]:
        result = run_vlns(
            state,
            self.generator,
            self.evaluator,
            self.applier,
            self.validator,
            max_iterations=self.config.max_iterations,
        )
        return result.state, _reference_iteration_results(result.trace)

    def solve_with_trace(
        self, state: SearchState
    ) -> tuple[SearchState, SearchTrace]:
        result = run_vlns(
            state,
            self.generator,
            self.evaluator,
            self.applier,
            self.validator,
            max_iterations=self.config.max_iterations,
        )
        return result.state, result.trace


def _reference_iteration_results(
    trace: SearchTrace,
) -> tuple[ReferenceIterationResult, ...]:
    by_iteration: dict[int, list[PhaseTrace]] = {}
    for phase in trace.phases:
        by_iteration.setdefault(phase.iteration, []).append(phase)

    results: list[ReferenceIterationResult] = []
    for iteration, phases in sorted(by_iteration.items()):
        lookup = {phase.phase: phase for phase in phases}
        drop = lookup["drop"]
        add = lookup["add"]
        swap = lookup.get("swap")
        results.append(
            ReferenceIterationResult(
                iteration=iteration,
                drop_evaluated=drop.evaluated,
                add_evaluated=add.evaluated,
                swap_evaluated=0 if swap is None else swap.evaluated,
                drop_accepted=drop.accepted,
                add_accepted=add.accepted,
                swap_accepted=False if swap is None else swap.accepted,
                stopped=not any(p.accepted for p in phases),
            )
        )
    return tuple(results)

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




@dataclass(frozen=True)
class SearchRunResult:
    """Shared result for all selector-controlled VLNS experiments."""

    state: SearchState
    trace: SearchTrace
    iterations: int
    accepted_moves: int


def run_vlns(
    state: SearchState,
    generator: PhaseMoveGenerator,
    evaluator: MoveEvaluator,
    applier: MoveApplier,
    validator: StateValidator,
    *,
    selector: Selector | None = None,
    exact_evaluations_per_phase: int | None = None,
    max_iterations: int = 200,
) -> SearchRunResult:
    """Run the canonical Drop -> Add -> conditional Swap search loop.

    With no selector, this is Vanilla VLNS and every candidate is evaluated.
    With a selector, only its ranked prefix receives exact evaluation.
    """
    if max_iterations < 0:
        raise ValueError("max_iterations must be non-negative")
    if exact_evaluations_per_phase is not None and exact_evaluations_per_phase < 0:
        raise ValueError("exact_evaluations_per_phase must be non-negative")

    phases: list[PhaseTrace] = []
    accepted_moves = 0

    for iteration in range(max_iterations):
        drop = _run_canonical_phase(
            state, iteration, "drop", generator, evaluator, applier, validator,
            selector, exact_evaluations_per_phase,
        )
        state = drop.state
        phases.append(drop.trace)
        drop_accepted = drop.accepted
        accepted_moves += int(drop_accepted)

        add = _run_canonical_phase(
            state, iteration, "add", generator, evaluator, applier, validator,
            selector, exact_evaluations_per_phase,
        )
        state = add.state
        phases.append(add.trace)
        add_accepted = add.accepted
        accepted_moves += int(add_accepted)

        swap_accepted = False
        if not drop_accepted and not add_accepted:
            swap = _run_canonical_phase(
                state, iteration, "swap", generator, evaluator, applier, validator,
                selector, exact_evaluations_per_phase,
            )
            state = swap.state
            phases.append(swap.trace)
            swap_accepted = swap.accepted
            accepted_moves += int(swap_accepted)

        if not (drop_accepted or add_accepted or swap_accepted):
            break

    return SearchRunResult(
        state=state,
        trace=SearchTrace(tuple(phases)),
        iterations=iteration + 1 if max_iterations else 0,
        accepted_moves=accepted_moves,
    )


@dataclass(frozen=True)
class _PhaseRunResult:
    state: SearchState
    trace: PhaseTrace
    accepted: bool


def _run_canonical_phase(
    state: SearchState,
    iteration: int,
    phase: str,
    generator: PhaseMoveGenerator,
    evaluator: MoveEvaluator,
    applier: MoveApplier,
    validator: StateValidator,
    selector: Selector | None,
    exact_evaluations_per_phase: int | None,
) -> _PhaseRunResult:
    candidates = list(generator.generate_phase(state, phase))
    ranked = list(candidates) if selector is None else list(
        selector.rank(state, candidates)
    )
    selected = (
        ranked
        if selector is None or exact_evaluations_per_phase is None
        else ranked[:exact_evaluations_per_phase]
    )
    best = choose_best_improvement(evaluator, state, selected)

    if best is None:
        return _PhaseRunResult(
            state=state,
            trace=PhaseTrace(
                iteration=iteration,
                phase=phase,
                candidates=len(candidates),
                evaluated=len(selected),
                accepted=False,
                best_delta=None,
            ),
            accepted=False,
        )

    new_state = applier.apply(state, best[0])
    validation = validator.validate(new_state)
    if not validation.valid:
        raise ValueError(
            f"accepted move produced invalid state: {validation.violations}"
        )
    return _PhaseRunResult(
        state=new_state,
        trace=PhaseTrace(
            iteration=iteration,
            phase=phase,
            candidates=len(candidates),
            evaluated=len(selected),
            accepted=True,
            best_delta=best[1].delta,
        ),
        accepted=True,
    )


def choose_best_improvement(
    evaluator: MoveEvaluator,
    state: SearchState,
    candidates: Sequence[CandidateAction],
) -> tuple[CandidateAction, Evaluation] | None:
    """Evaluate all candidates and return the strictly improving best move."""

    best: tuple[CandidateAction, Evaluation] | None = None
    for action in candidates:
        evaluation = evaluator.evaluate(state, action)
        if not evaluation.feasible or evaluation.delta >= -1e-6:
            continue
        if best is None or evaluation.delta < best[1].delta:
            best = (action, evaluation)
    return best



def _phase_trace(
    iteration: int,
    phase: str,
    candidates: int,
    best: tuple[CandidateAction, Evaluation] | None,
) -> PhaseTrace:
    return PhaseTrace(
        iteration=iteration,
        phase=phase,
        candidates=candidates,
        evaluated=candidates,
        accepted=best is not None,
        best_delta=None if best is None else best[1].delta,
    )
