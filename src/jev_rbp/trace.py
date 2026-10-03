"""Deterministic trace records for reference VLNS reproduction."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhaseTrace:
    """One evaluated reference phase within an iteration."""

    iteration: int
    phase: str
    candidates: int
    evaluated: int
    accepted: bool
    best_delta: float | None


@dataclass(frozen=True)
class SearchTrace:
    """Complete deterministic trace of a reference-shaped VLNS run."""

    phases: tuple[PhaseTrace, ...]

    def as_rows(self) -> tuple[dict[str, object], ...]:
        """Return stable rows suitable for JSON/CSV experiment logs."""
        return tuple(
            {
                "iteration": item.iteration,
                "phase": item.phase,
                "candidates": item.candidates,
                "evaluated": item.evaluated,
                "accepted": item.accepted,
                "best_delta": item.best_delta,
            }
            for item in self.phases
        )
