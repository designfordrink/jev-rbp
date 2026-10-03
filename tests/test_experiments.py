from jev_rbp.dataset import DatasetRow
from jev_rbp.experiments import grouped_ranking_metrics, split_by_instance


def row(instance, iteration, phase, index, delta):
    return DatasetRow(
        iteration=iteration,
        phase=phase,
        candidate_index=index,
        action_type="Drop",
        action_payload=(index,),
        features={"x": float(index)},
        feasible=True,
        objective_before=10.0,
        objective_after=10.0 + delta,
        delta=delta,
        is_improving=delta < 0,
        instance_id=instance,
    )


def test_split_by_instance_prevents_row_leakage():
    rows = (row("a", 0, "drop", 0, -2.0), row("b", 0, "drop", 0, -3.0))
    train, test = split_by_instance(rows, test_instance_ids={"b"})
    assert [item.instance_id for item in train] == ["a"]
    assert [item.instance_id for item in test] == ["b"]


def test_grouped_metrics_measure_top_k_and_regret():
    rows = (
        row("a", 0, "drop", 0, -1.0),
        row("a", 0, "drop", 1, -5.0),
        row("a", 0, "drop", 2, -2.0),
    )
    metrics = grouped_ranking_metrics(rows, lambda item: item.features["x"], k=2)
    assert metrics.pools == 1
    assert metrics.top_k_hit_rate == 1.0
    assert metrics.mean_regret == 0.0
