from dataclasses import dataclass

from jev_rbp.actions import AddAction, DropAction, SwapAction
from jev_rbp.core import Evaluation, ValidationResult
from jev_rbp.selectors import IdentitySelector
from jev_rbp.selector_vlns import SelectorVLNSConfig, SelectorVLNSSolver


@dataclass(frozen=True)
class State:
    value: float


class Generator:
    def generate_phase(self, state, phase):
        if phase == "drop":
            return [DropAction(1), DropAction(2), DropAction(3)]
        if phase == "add":
            return [AddAction(1, 2, "Manifest")]
        return [SwapAction(1, 2, 3, "Manifest")]


class Evaluator:
    def evaluate(self, state, action):
        if isinstance(action, DropAction):
            delta = {1: -1.0, 2: -5.0, 3: -2.0}[action.block_id]
        else:
            delta = 0.0
        return Evaluation(state.value, state.value + delta, True)


class Applier:
    def apply(self, state, action):
        return State(state.value + Evaluator().evaluate(state, action).delta)


class Validator:
    def validate(self, state):
        return ValidationResult(True)


def test_identity_selector_respects_exact_evaluation_budget():
    solver = SelectorVLNSSolver(
        Generator(),
        IdentitySelector(),
        Evaluator(),
        Applier(),
        Validator(),
        SelectorVLNSConfig(max_iterations=1, exact_evaluations_per_phase=1),
    )

    state, trace = solver.solve_with_trace(State(10.0))

    assert state.value == 9.0
    assert trace.phases[0].phase == "drop"
    assert trace.phases[0].candidates == 3
    assert trace.phases[0].evaluated == 1
    assert trace.phases[0].best_delta == -1.0


def test_full_phase_budget_recovers_best_improvement():
    solver = SelectorVLNSSolver(
        Generator(),
        IdentitySelector(),
        Evaluator(),
        Applier(),
        Validator(),
        SelectorVLNSConfig(max_iterations=1, exact_evaluations_per_phase=3),
    )

    state, trace = solver.solve_with_trace(State(10.0))

    assert state.value == 5.0
    assert trace.phases[0].evaluated == 3
    assert trace.phases[0].best_delta == -5.0


def test_zero_budget_means_evaluate_all_candidates():
    solver = SelectorVLNSSolver(
        Generator(),
        IdentitySelector(),
        Evaluator(),
        Applier(),
        Validator(),
        SelectorVLNSConfig(max_iterations=1, exact_evaluations_per_phase=0),
    )

    _, trace = solver.solve_with_trace(State(10.0))

    assert trace.phases[0].evaluated == 3
