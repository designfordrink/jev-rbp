from dataclasses import dataclass

from jev_rbp.core import ValidationResult
from jev_rbp.experiment_runner import (
    ExperimentCase,
    run_selector_case,
    run_selector_suite,
)
from jev_rbp.problem import RBPInstance, Settings, Solution
from jev_rbp.selectors import IdentitySelector, RandomSelector


@dataclass(frozen=True)
class EmptyGenerator:
    def generate_phase(self, state, phase):
        return []


@dataclass(frozen=True)
class EmptyEvaluator:
    def evaluate(self, state, action):
        raise AssertionError("no candidate should be evaluated")


@dataclass(frozen=True)
class EmptyApplier:
    def apply(self, state, action):
        raise AssertionError("no action should be applied")


@dataclass(frozen=True)
class EmptyValidator:
    def validate(self, state):
        return ValidationResult(True)


def case(name="tiny"):
    return ExperimentCase(
        instance_id=name,
        instance=RBPInstance(nodes={}, links={}, demands={}, settings=Settings()),
        initial_solution=Solution(),
        generator=EmptyGenerator(),
        evaluator=EmptyEvaluator(),
        applier=EmptyApplier(),
        validator=EmptyValidator(),
    )


def test_runner_keeps_exact_evaluation_budget_accounting():
    result = run_selector_case(
        case(),
        IdentitySelector(),
        selector_name="identity",
        exact_evaluation_budget=1,
        max_iterations=1,
    )

    assert result.exact_evaluations == 0
    assert result.accepted_moves == 0
    assert result.benchmark_feasible is True


def test_suite_runs_each_selector_on_each_instance():
    results = run_selector_suite(
        [case("a"), case("b")],
        {
            "identity": lambda _: IdentitySelector(),
            "random": lambda _: RandomSelector(seed=0),
        },
        exact_evaluation_budget=1,
        max_iterations=1,
    )

    assert [(item.instance_id, item.selector) for item in results] == [
        ("a", "identity"),
        ("a", "random"),
        ("b", "identity"),
        ("b", "random"),
    ]


def test_runner_supports_canonical_vanilla_vlns():
    result = run_selector_case(
        case(),
        None,
        selector_name="vanilla-vlns",
        exact_evaluation_budget=None,
        max_iterations=1,
    )

    assert result.exact_evaluations == 0
    assert result.benchmark_feasible is True
