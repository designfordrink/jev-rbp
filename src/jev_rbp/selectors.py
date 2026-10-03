"""Selector baselines used for controlled experiments."""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from .core import CandidateAction


class RandomSelector:
    """Deterministic-with-seed random selector."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

    def rank(
        self, state: object, candidates: Sequence[CandidateAction]
    ) -> Sequence[CandidateAction]:
        ranked = list(candidates)
        self._rng.shuffle(ranked)
        return ranked


class IdentitySelector:
    """Preserve candidate order; useful as a deterministic baseline."""

    def rank(
        self, state: object, candidates: Sequence[CandidateAction]
    ) -> Sequence[CandidateAction]:
        return list(candidates)


class GreedySelector:
    """Rank candidates by a cheap, user-supplied heuristic score.

    Lower scores are ranked first. The score function is deliberately separate
    from the exact evaluator: a greedy selector may use inexpensive state and
    candidate features, but it must not consume the exact-evaluation budget.
    Python's stable sort preserves candidate-generator order for equal scores.
    """

    def __init__(
        self,
        score: Callable[[object, CandidateAction], float],
    ) -> None:
        self._score = score

    def rank(
        self, state: object, candidates: Sequence[CandidateAction]
    ) -> Sequence[CandidateAction]:
        return sorted(candidates, key=lambda candidate: self._score(state, candidate))
