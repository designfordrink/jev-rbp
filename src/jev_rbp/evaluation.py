"""Exact evaluation boundary for candidate moves."""

from __future__ import annotations

from .core import CandidateAction, Evaluation


class ExactEvaluator:
    """Authoritative evaluator used after candidate selection."""

    def evaluate(self, state: object, action: CandidateAction) -> Evaluation:
        raise NotImplementedError
