"""Metrics for controlled selector experiments."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Sequence

from .dataset import DatasetRow


@dataclass(frozen=True)
class RankingMetrics:
    """Aggregate ranking metrics over independent candidate pools."""

    pools: int
    top_k_hit_rate: float
    mean_regret: float


def split_by_instance(
    rows: Sequence[DatasetRow],
    *,
    test_instance_ids: set[str],
) -> tuple[tuple[DatasetRow, ...], tuple[DatasetRow, ...]]:
    """Split rows without leaking candidate observations across instances."""

    train = tuple(row for row in rows if row.instance_id not in test_instance_ids)
    test = tuple(row for row in rows if row.instance_id in test_instance_ids)
    return train, test


def grouped_ranking_metrics(
    rows: Sequence[DatasetRow],
    score: Callable[[DatasetRow], float],
    *,
    k: int = 1,
) -> RankingMetrics:
    """Measure Top-K optimal-delta coverage and exact-delta regret.

    A pool is one (instance, iteration, phase) group. Infeasible candidates
    remain in the ranking, but cannot be the oracle. Ties count as hits:
    selecting any candidate within 1e-6 of the best feasible delta is optimal.
    """

    if k <= 0:
        raise ValueError("k must be positive")

    groups: dict[tuple[str, int, str], list[DatasetRow]] = defaultdict(list)
    for row in rows:
        groups[(row.instance_id, row.iteration, row.phase)].append(row)

    hits = 0
    regrets: list[float] = []

    for pool in groups.values():
        feasible = [row for row in pool if row.feasible]
        if not feasible:
            continue
        oracle_delta = min(row.delta for row in feasible)
        ranked = sorted(
            enumerate(pool),
            key=lambda item: (score(item[1]), item[0]),
        )
        selected = ranked[:k]
        if any(
            row.feasible and abs(row.delta - oracle_delta) <= 1e-6
            for _, row in selected
        ):
            hits += 1
        chosen = next(
            (row for _, row in ranked if row.feasible),
            None,
        )
        if chosen is not None:
            regrets.append(chosen.delta - oracle_delta)

    pool_count = len(regrets)
    return RankingMetrics(
        pools=pool_count,
        top_k_hit_rate=hits / pool_count if pool_count else 0.0,
        mean_regret=sum(regrets) / pool_count if pool_count else 0.0,
    )
