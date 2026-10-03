from jev_rbp.actions import DropAction
from jev_rbp.core import CandidateAction
from jev_rbp.dataset import DatasetRow
from jev_rbp.jev import LinearJEVSelector, fit_linear_jev
from jev_rbp.problem import CommodityType


def _row(index: int, x: float, delta: float) -> DatasetRow:
    return DatasetRow(
        iteration=0,
        phase="drop",
        candidate_index=index,
        action_type="Drop",
        action_payload=(index,),
        features={"x": x},
        feasible=True,
        objective_before=10.0,
        objective_after=10.0 + delta,
        delta=delta,
        is_improving=delta < -1e-6,
    )


def test_linear_jev_learns_direction_of_delta():
    rows = tuple(_row(index, float(index), -float(index)) for index in range(1, 6))
    model = fit_linear_jev(rows)

    assert model.predict_features({"x": 5.0}) < model.predict_features({"x": 1.0})


def test_linear_jev_selector_ranks_without_exact_evaluator():
    rows = tuple(_row(index, float(index), -float(index)) for index in range(1, 6))
    model = fit_linear_jev(rows)

    def features(state, action: CandidateAction, phase: str, index: int):
        return {"x": float(action.block_id)}

    selector = LinearJEVSelector(model, features)
    candidates = [DropAction(1), DropAction(5), DropAction(3)]

    ranked = selector.rank(object(), candidates)

    assert [action.block_id for action in ranked] == [5, 3, 1]


def test_linear_jev_supports_multiple_action_features():
    rows = (
        DatasetRow(
            0,
            "add",
            0,
            "Add",
            (1, 2, CommodityType.MERCHANDISE),
            {"x": 0.0, "y": 1.0},
            True,
            10.0,
            9.0,
            -1.0,
            True,
        ),
        DatasetRow(
            0,
            "add",
            1,
            "Add",
            (1, 3, CommodityType.MERCHANDISE),
            {"x": 1.0, "y": 0.0},
            True,
            10.0,
            8.0,
            -2.0,
            True,
        ),
    )
    model = fit_linear_jev(rows)

    assert isinstance(model.predict_features({"x": 1.0}), float)
