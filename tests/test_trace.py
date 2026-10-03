from dataclasses import dataclass

from jev_rbp.actions import AddAction, DropAction, SwapAction
from jev_rbp.core import Evaluation, ValidationResult
from jev_rbp.problem import CommodityType
from jev_rbp.vlns import ReferenceVLNSSolver, VLNSConfig


@dataclass(frozen=True)
class State:
    value: float


class PhaseGenerator:
    def generate_phase(self, state, phase):
        if phase == "drop":
            return [DropAction(1)]
        if phase == "add":
            return [AddAction(1, 2, CommodityType.MERCHANDISE)]
        if phase == "swap":
            return [SwapAction(1, 2, 3, CommodityType.MERCHANDISE)]
        raise AssertionError(phase)


class Evaluator:
    def evaluate(self, state, action):
        if isinstance(action, DropAction):
            return Evaluation(state.value, state.value, True)
        if isinstance(action, AddAction):
            return Evaluation(state.value, state.value, True)
        return Evaluation(state.value, state.value - 2.0, True)


class Applier:
    def apply(self, state, action):
        return State(state.value - 2.0)


class Validator:
    def validate(self, state):
        return ValidationResult(True)


def test_reference_trace_reaches_swap_only_after_drop_and_add_fail():
    solver = ReferenceVLNSSolver(
        PhaseGenerator(),
        Evaluator(),
        Applier(),
        Validator(),
        VLNSConfig(max_iterations=1),
    )

    state, trace = solver.solve_with_trace(State(10.0))

    assert state.value == 8.0
    assert [(row.phase, row.accepted) for row in trace.phases] == [
        ("drop", False),
        ("add", False),
        ("swap", True),
    ]
    assert trace.phases[-1].best_delta == -2.0
    assert trace.as_rows()[-1]["phase"] == "swap"


def test_reference_trace_does_not_evaluate_swap_after_an_accepted_drop():
    class DropWins(Evaluator):
        def evaluate(self, state, action):
            if isinstance(action, DropAction):
                return Evaluation(state.value, state.value - 1.0, True)
            return Evaluation(state.value, state.value, True)

    solver = ReferenceVLNSSolver(
        PhaseGenerator(),
        DropWins(),
        Applier(),
        Validator(),
        VLNSConfig(max_iterations=1),
    )

    _, trace = solver.solve_with_trace(State(10.0))

    assert [row.phase for row in trace.phases] == ["drop", "add"]
    assert trace.phases[0].accepted
    assert not trace.phases[1].accepted
