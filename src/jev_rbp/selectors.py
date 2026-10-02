"""Selector baselines used for controlled experiments."""

from __future__ import annotations

import random
from typing import Sequence

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
