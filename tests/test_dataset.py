from dataclasses import dataclass

from jev_rbp.actions import DropAction
from jev_rbp.core import Evaluation
from jev_rbp.dataset import collect_jev_dataset
from jev_rbp.problem import RBPInstance, Solution, Settings
from jev_rbp.routing import DijkstraRouter


@dataclass
class Generator:
    def generate_phase(self, state, phase):
        if phase == "drop":
            return [DropAction(1), DropAction(2)]
        return []


class Evaluator:
    def evaluate(self, state, action):
        delta = -2.0 if action.block_id == 1 else 1.0
        return Evaluation(state.value, state.value + delta, delta < 0)


class Applier:
    def apply(self, state, action):
        return state


@dataclass
class State(Solution):
    value: float = 10.0


def test_dataset_collects_all_candidates_with_exact_labels():
    instance = RBPInstance(nodes={}, links={}, demands={}, settings=Settings())
    rows = collect_jev_dataset(
        State(),
        Generator(),
        Evaluator(),
        Applier(),
        instance,
        DijkstraRouter(instance),
        max_iterations=1,
        feature_extractor=lambda state, action, phase, index: {
            "candidate_index": float(index)
        },
    )

    assert len(rows) == 2
    assert [row.candidate_index for row in rows] == [0, 1]
    assert rows[0].delta == -2.0
    assert rows[0].feasible is True
    assert rows[0].is_improving is True
    assert rows[1].feasible is False


def test_dataset_uses_reference_phase_order_and_stops_after_no_improvement():
    class OrderedGenerator:
        def generate_phase(self, state, phase):
            return [DropAction(1)] if phase == "drop" else []

    rows = collect_jev_dataset(
        State(),
        OrderedGenerator(),
        Evaluator(),
        Applier(),
        RBPInstance(nodes={}, links={}, demands={}, settings=Settings()),
        DijkstraRouter(RBPInstance(nodes={}, links={}, demands={}, settings=Settings())),
        max_iterations=1,
        feature_extractor=lambda state, action, phase, index: {"phase": float(index)},
    )

    assert [row.phase for row in rows] == ["drop"]
