from dataclasses import dataclass

from jev_rbp.actions import DropAction
from jev_rbp.core import Evaluation, ValidationResult
from jev_rbp.vlns import VLNSConfig, VLNSSolver


@dataclass(frozen=True)
class State:
    value: float


class Generator:
    def generate(self, state):
        return [DropAction(1), DropAction(2)]


class Evaluator:
    def evaluate(self, state, action):
        return Evaluation(
            objective_before=state.value,
            objective_after=state.value - (2.0 if action.block_id == 2 else 1.0),
            feasible=True,
        )


class Applier:
    def apply(self, state, action):
        return State(state.value - 2.0)


class Validator:
    def validate(self, state):
        return ValidationResult(valid=True)


def test_vlns_chooses_best_improvement():
    solver = VLNSSolver(
        Generator(), Evaluator(), Applier(), Validator(), VLNSConfig(max_iterations=1)
    )
    state, result = solver.step(State(10.0), 0)
    assert result.accepted
    assert result.best_delta == -2.0
    assert state.value == 8.0


def test_vlns_stops_when_no_improvement():
    class NoImprovement(Evaluator):
        def evaluate(self, state, action):
            return Evaluation(state.value, state.value, True)

    solver = VLNSSolver(
        Generator(), NoImprovement(), Applier(), Validator()
    )
    state, result = solver.step(State(10.0), 0)
    assert not result.accepted
    assert state.value == 10.0
