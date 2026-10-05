"""Controlled multi-instance experiments for JEV selectors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from .benchmark import BenchmarkAuthority
from .core import Selector
from .dataset import DatasetRow
from .problem import RBPInstance, Solution
from .selector_vlns import SelectorVLNSConfig, SelectorVLNSSolver
from .vlns import MoveApplier, MoveEvaluator, PhaseMoveGenerator, StateValidator


@dataclass(frozen=True)
class ExperimentCase:
    """One fixed RBP instance and its shared search components."""

    instance_id: str
    instance: RBPInstance
    initial_solution: Solution
    generator: PhaseMoveGenerator
    evaluator: MoveEvaluator
    applier: MoveApplier
    validator: StateValidator


@dataclass(frozen=True)
class SelectorRunResult:
    """Outcome of one selector on one instance under one exact-evaluation budget.

    ``selector=None`` is canonical Vanilla VLNS: the engine evaluates the
    complete candidate pool instead of ranking it with a selector.
    """

    selector: str
    instance_id: str
    exact_evaluation_budget: int | None
    exact_evaluations: int
    accepted_moves: int
    iterations: int
    final_operating_cost: float
    final_stress_score: float
    benchmark_feasible: bool


SelectorFactory = Callable[[ExperimentCase], Selector | None]


def run_selector_case(
    case: ExperimentCase,
    selector: Selector | None,
    *,
    selector_name: str,
    exact_evaluation_budget: int | None,
    max_iterations: int = 200,
) -> SelectorRunResult:
    """Run one selector while keeping every other search component fixed.

    ``selector=None`` runs canonical Vanilla VLNS (full candidate evaluation).
    The benchmark evaluation happens only after the search and is not counted
    as an exact move evaluation. This keeps the search-budget accounting
    comparable across selectors.
    """

    solver = SelectorVLNSSolver(
        generator=case.generator,
        selector=selector,
        evaluator=case.evaluator,
        applier=case.applier,
        validator=case.validator,
        config=SelectorVLNSConfig(
            max_iterations=max_iterations,
            exact_evaluations_per_phase=exact_evaluation_budget,
        ),
    )
    final_state, iterations = solver.solve(case.initial_solution)

    exact_evaluations = sum(
        result.drop_evaluated
        + result.add_evaluated
        + result.swap_evaluated
        for result in iterations
    )
    accepted_moves = sum(1 for result in iterations if result.accepted)

    report = BenchmarkAuthority(case.instance).validate(final_state)
    if report.cost is None or report.stress is None:
        raise RuntimeError("benchmark authority returned no cost/stress report")

    return SelectorRunResult(
        selector=selector_name,
        instance_id=case.instance_id,
        exact_evaluation_budget=exact_evaluation_budget,
        exact_evaluations=exact_evaluations,
        accepted_moves=accepted_moves,
        iterations=len(iterations),
        final_operating_cost=report.cost.total,
        final_stress_score=report.stress.stress_score,
        benchmark_feasible=report.feasible,
    )


def run_selector_suite(
    cases: Sequence[ExperimentCase],
    selector_factories: Mapping[str, SelectorFactory],
    *,
    exact_evaluation_budget: int | None,
    max_iterations: int = 200,
) -> tuple[SelectorRunResult, ...]:
    """Run the same selector suite over multiple independent instances."""

    results: list[SelectorRunResult] = []
    for case in cases:
        for name, factory in selector_factories.items():
            selector = factory(case)
            results.append(
                run_selector_case(
                    case,
                    selector,
                    selector_name=name,
                    exact_evaluation_budget=exact_evaluation_budget,
                    max_iterations=max_iterations,
                )
            )
    return tuple(results)


def training_rows_for_instances(
    rows: Sequence[DatasetRow],
    *,
    train_instance_ids: set[str],
) -> tuple[DatasetRow, ...]:
    """Return only rows from training instances.

    Keeping this helper explicit makes accidental row-level train/test leakage
    harder when experiment scripts are assembled.
    """

    return tuple(row for row in rows if row.instance_id in train_instance_ids)
