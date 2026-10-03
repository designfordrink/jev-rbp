"""Deterministic training-dataset generation for JEV selectors."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .actions import AddAction, DropAction, SwapAction
from .core import CandidateAction, Evaluation
from .problem import RBPInstance, Solution
from .routing import DijkstraRouter
from .vlns import MoveApplier, MoveEvaluator, PhaseMoveGenerator, SearchState


@dataclass(frozen=True)
class DatasetRow:
    """One candidate/action observation for JEV training."""

    iteration: int
    phase: str
    candidate_index: int
    action_type: str
    action_payload: tuple[object, ...]
    features: dict[str, float]
    feasible: bool
    objective_before: float
    objective_after: float
    delta: float
    is_improving: bool


FeatureExtractor = Callable[[Solution, CandidateAction, str, int], dict[str, float]]


def collect_jev_dataset(
    initial_state: SearchState,
    generator: PhaseMoveGenerator,
    evaluator: MoveEvaluator,
    applier: MoveApplier,
    instance: RBPInstance,
    router: DijkstraRouter,
    *,
    max_iterations: int = 200,
    feature_extractor: FeatureExtractor | None = None,
) -> tuple[DatasetRow, ...]:
    """Collect exact labels while replaying the reference-shaped VLNS.

    Every candidate in every reached phase is evaluated. The accepted action is
    selected with the same strict best-improvement rule used by the baseline.
    The resulting rows are therefore labels for the *local action* decision,
    not labels for the final solution.
    """

    if not isinstance(initial_state, Solution):
        raise TypeError("JEV dataset generation currently expects an RBP Solution")

    extract = feature_extractor or make_rbp_feature_extractor(instance, router)
    state = initial_state
    rows: list[DatasetRow] = []

    for iteration in range(max_iterations):
        state, phase_rows, accepted_drop = _collect_phase(
            state, iteration, "drop", generator, evaluator, applier, extract
        )
        rows.extend(phase_rows)

        state, phase_rows, accepted_add = _collect_phase(
            state, iteration, "add", generator, evaluator, applier, extract
        )
        rows.extend(phase_rows)

        accepted_swap = False
        if not accepted_drop and not accepted_add:
            state, phase_rows, accepted_swap = _collect_phase(
                state, iteration, "swap", generator, evaluator, applier, extract
            )
            rows.extend(phase_rows)

        if not (accepted_drop or accepted_add or accepted_swap):
            break

    return tuple(rows)


def write_jsonl(rows: tuple[DatasetRow, ...], path: str | Path) -> None:
    """Write deterministic dataset rows as UTF-8 JSON Lines."""

    destination = Path(path)
    with destination.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), sort_keys=True))
            handle.write("\n")


def _collect_phase(
    state: Solution,
    iteration: int,
    phase: str,
    generator: PhaseMoveGenerator,
    evaluator: MoveEvaluator,
    applier: MoveApplier,
    feature_extractor: FeatureExtractor,
) -> tuple[Solution, list[DatasetRow], bool]:
    candidates = list(generator.generate_phase(state, phase))
    observations: list[tuple[CandidateAction, Evaluation]] = []
    rows: list[DatasetRow] = []

    for candidate_index, action in enumerate(candidates):
        evaluation = evaluator.evaluate(state, action)
        observations.append((action, evaluation))
        rows.append(
            DatasetRow(
                iteration=iteration,
                phase=phase,
                candidate_index=candidate_index,
                action_type=action.action_type,
                action_payload=action.payload,
                features=feature_extractor(
                    state, action, phase, candidate_index
                ),
                feasible=evaluation.feasible,
                objective_before=evaluation.objective_before,
                objective_after=evaluation.objective_after,
                delta=evaluation.delta,
                is_improving=evaluation.feasible and evaluation.delta < -1e-6,
            )
        )

    best = _best_improvement(observations)
    if best is None:
        return state, rows, False

    new_state = applier.apply(state, best[0])
    return new_state, rows, True


def _best_improvement(
    evaluations: list[tuple[CandidateAction, Evaluation]],
) -> tuple[CandidateAction, Evaluation] | None:
    feasible = [
        item
        for item in evaluations
        if item[1].feasible and item[1].delta < -1e-6
    ]
    if not feasible:
        return None
    return min(feasible, key=lambda item: item[1].delta)


def make_rbp_feature_extractor(
    instance: RBPInstance,
    router: DijkstraRouter,
) -> FeatureExtractor:
    """Build a cheap RBP feature extractor with no exact-evaluation access."""

    def extract(
        state: Solution,
        action: CandidateAction,
        phase: str,
        candidate_index: int,
    ) -> dict[str, float]:
        features = {
            "phase_drop": float(phase == "drop"),
            "phase_add": float(phase == "add"),
            "phase_swap": float(phase == "swap"),
            "candidate_index": float(candidate_index),
            "open_block_count": float(len(state.blocks)),
            "demand_count": float(len(instance.demands)),
        }

        if isinstance(action, DropAction):
            block = state.blocks.get(action.block_id)
            if block is None:
                return features
            features.update(
                {
                    "drop_block_volume": float(block.volume),
                    "drop_distance": _distance(
                        router, block.from_yard_id, block.to_yard_id
                    ),
                    "drop_outgoing_degree": _outgoing_degree(
                        state, block.from_yard_id
                    ),
                }
            )
        elif isinstance(action, AddAction):
            features.update(
                {
                    "add_distance": _distance(
                        router, action.from_yard_id, action.to_yard_id
                    ),
                    "add_outgoing_degree": _outgoing_degree(
                        state, action.from_yard_id
                    ),
                }
            )
        elif isinstance(action, SwapAction):
            dropped = state.blocks.get(action.drop_block_id)
            if dropped is not None:
                features.update(
                    {
                        "drop_block_volume": float(dropped.volume),
                        "drop_distance": _distance(
                            router, dropped.from_yard_id, dropped.to_yard_id
                        ),
                        "drop_outgoing_degree": _outgoing_degree(
                            state, dropped.from_yard_id
                        ),
                    }
                )
            features.update(
                {
                    "add_distance": _distance(
                        router, action.add_from_yard_id, action.add_to_yard_id
                    ),
                    "add_outgoing_degree": _outgoing_degree(
                        state, action.add_from_yard_id
                    ),
                }
            )

        return features

    return extract


def _distance(router: DijkstraRouter, from_yard_id: int, to_yard_id: int) -> float:
    route = router.shortest_path(from_yard_id, to_yard_id)
    return float("inf") if route is None else float(route.distance)


def _outgoing_degree(state: Solution, yard_id: int) -> int:
    return sum(
        1
        for block in state.blocks.values()
        if block.from_yard_id == yard_id
    )
