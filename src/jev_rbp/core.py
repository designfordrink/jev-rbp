"""Small, solver-independent interfaces used by the research prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class CandidateAction:
    """An atomic proposed change to a search state."""

    action_type: str
    payload: tuple[Any, ...]


@dataclass(frozen=True)
class Evaluation:
    """Exact or authoritative evaluation of an action."""

    objective_before: float
    objective_after: float
    feasible: bool

    @property
    def delta(self) -> float:
        return self.objective_after - self.objective_before


@dataclass(frozen=True)
class ValidationResult:
    """Independent feasibility result."""

    valid: bool
    violations: tuple[str, ...] = ()


class CandidateGenerator(Protocol):
    def generate(self, state: Any) -> Sequence[CandidateAction]: ...


class Selector(Protocol):
    def rank(
        self, state: Any, candidates: Sequence[CandidateAction]
    ) -> Sequence[CandidateAction]: ...


class Evaluator(Protocol):
    def evaluate(self, state: Any, action: CandidateAction) -> Evaluation: ...


class Validator(Protocol):
    def validate(self, solution: Any) -> ValidationResult: ...
