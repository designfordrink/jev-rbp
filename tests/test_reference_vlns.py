from dataclasses import dataclass

from jev_rbp.actions import AddAction, DropAction, SwapAction
from jev_rbp.core import Evaluation, ValidationResult
from jev_rbp.problem import CommodityType
from jev_rbp.vlns import ReferenceVLNSSolver, VLNSConfig


@dataclass(frozen=True)
class State:
    value: float


class Generator:
    def generate_phase(self, state, phase):
        if phase == "drop":
            return [DropAction(1)]
        if phase == "add":
            return [AddAction(1, 2, CommodityType.MERCHANDISE)]
        return [SwapAction(1, 2, 3, CommodityType.MERCHANDISE)]


class Evaluator:
    def evaluate(self, state, action):
        deltas = {"drop": -2.0, "add": -1.0, "swap": -5.0}
        return Evaluation(state.value, state.value + deltas[action.action_type], True)


class Applier:
    def apply(self, state, action):
        return State(state.value - 2.0 if action.action_type == "drop" else state.value - 1.0)


class Validator:
    def validate(self, state):
        return ValidationResult(valid=True)


def test_reference_vlns_runs_drop_then_add_and_skips_swap():
    solver = ReferenceVLNSSolver(
        Generator(), Evaluator(), Applier(), Validator(), VLNSConfig(max_iterations=1)
    )

    state, result = solver.step(State(10.0), 0)

    assert state.value == 7.0
    assert result.drop_accepted
    assert result.add_accepted
    assert not result.swap_accepted
    assert result.swap_evaluated == 0
    assert not result.stopped


def test_reference_vlns_uses_swap_only_when_drop_and_add_fail():
    class NoImprovement(Evaluator):
        def evaluate(self, state, action):
            if action.action_type == "swap":
                return Evaluation(state.value, state.value - 3.0, True)
            return Evaluation(state.value, state.value, True)

    solver = ReferenceVLNSSolver(
        Generator(), NoImprovement(), Applier(), Validator()
    )

    state, result = solver.step(State(10.0), 0)

    assert state.value == 9.0
    assert not result.drop_accepted
    assert not result.add_accepted
    assert result.swap_accepted
    assert result.swap_evaluated == 1
