"""JEV v0: a dependency-free linear learned action selector."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence

from .core import CandidateAction
from .dataset import DatasetRow, FeatureExtractor


@dataclass(frozen=True)
class LinearJEVModel:
    """Ridge-style linear model predicting exact move delta."""

    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    intercept: float

    def predict_features(self, features: dict[str, float]) -> float:
        values = []
        for name, mean, scale in zip(self.feature_names, self.means, self.scales):
            value = float(features.get(name, 0.0))
            values.append((value - mean) / scale)
        return self.intercept + sum(
            weight * value for weight, value in zip(self.weights, values)
        )


def fit_linear_jev(
    rows: Sequence[DatasetRow],
    *,
    ridge: float = 1e-6,
) -> LinearJEVModel:
    """Fit a deterministic linear predictor of exact objective delta.

    Feasible rows use their exact delta as the target. Infeasible rows use zero
    here; feasibility remains a separate label and is still checked by the
    exact evaluator/validator.
    """

    if not rows:
        raise ValueError("cannot fit JEV v0 on an empty dataset")
    if ridge < 0.0:
        raise ValueError("ridge must be non-negative")

    names = tuple(sorted({name for row in rows for name in row.features}))
    if not names:
        raise ValueError("dataset contains no features")

    raw = [[float(row.features.get(name, 0.0)) for name in names] for row in rows]
    targets = [float(row.delta) if row.feasible else 0.0 for row in rows]

    means = tuple(sum(column) / len(column) for column in zip(*raw))
    scales = tuple(
        max(
            sqrt(sum((row[index] - means[index]) ** 2 for row in raw) / len(raw)),
            1e-12,
        )
        for index in range(len(names))
    )
    normalized = [
        [(value - mean) / scale for value, mean, scale in zip(row, means, scales)]
        for row in raw
    ]

    # The model is intentionally tiny, so deterministic Gaussian elimination
    # avoids adding a heavyweight ML dependency for the first experiment.
    matrix_size = len(names) + 1
    gram = [[0.0 for _ in range(matrix_size)] for _ in range(matrix_size)]
    rhs = [0.0 for _ in range(matrix_size)]

    for row, target in zip(normalized, targets):
        vector = [1.0, *row]
        for i in range(matrix_size):
            rhs[i] += vector[i] * target
            for j in range(matrix_size):
                gram[i][j] += vector[i] * vector[j]

    for i in range(1, matrix_size):
        gram[i][i] += ridge

    solution = _solve_linear_system(gram, rhs)
    return LinearJEVModel(
        feature_names=names,
        means=means,
        scales=scales,
        intercept=solution[0],
        weights=tuple(solution[1:]),
    )


class LinearJEVSelector:
    """Rank candidates using a trained JEV model.

    The selector consumes only cheap features. It has no evaluator, validator,
    or exact objective access.
    """

    def __init__(
        self,
        model: LinearJEVModel,
        feature_extractor: FeatureExtractor,
    ) -> None:
        self.model = model
        self.feature_extractor = feature_extractor

    def rank(
        self,
        state: object,
        candidates: Sequence[CandidateAction],
    ) -> Sequence[CandidateAction]:
        scored = [
            (
                self.model.predict_features(
                    self.feature_extractor(
                        state,
                        action,
                        _phase_for_action(action),
                        index,
                    )
                ),
                index,
                action,
            )
            for index, action in enumerate(candidates)
        ]
        scored.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in scored]


def _phase_for_action(action: CandidateAction) -> str:
    action_type = action.action_type.lower()
    if action_type in {"drop", "add", "swap"}:
        return action_type
    raise ValueError(f"unknown action type: {action.action_type}")


def _solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = len(rhs)
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]

    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular feature matrix; increase ridge regularization")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]

        divisor = augmented[column][column]
        for index in range(column, size + 1):
            augmented[column][index] /= divisor

        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for index in range(column, size + 1):
                augmented[row][index] -= factor * augmented[column][index]

    return [augmented[index][size] for index in range(size)]
