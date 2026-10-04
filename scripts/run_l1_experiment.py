#!/usr/bin/env python3
"""Run the first controlled real-data RAS L1 JEV experiment.

This is a prototype experiment on demand slices from one public L1 physical
network. It is useful for exercising the real loader/search stack, but the
slices are not independent benchmark instances.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from jev_rbp.dataset import (
    collect_jev_dataset,
    make_rbp_feature_extractor,
    write_jsonl,
)
from jev_rbp.experiment_runner import ExperimentCase, run_selector_suite
from jev_rbp.experiments import grouped_ranking_metrics
from jev_rbp.jev import LinearJEVSelector, fit_linear_jev
from jev_rbp.io import load_instance
from jev_rbp.moves import (
    ExactRBPMoveEvaluator,
    MoveContext,
    RBPMoveApplier,
    RBPMoveGenerator,
    RBPMoveValidator,
)
from jev_rbp.rbp_selectors import RBPGreedySelector
from jev_rbp.routing import DijkstraRouter
from jev_rbp.selectors import IdentitySelector, RandomSelector
from jev_rbp.problem import (
    Block,
    BlockRoute,
    BlockingSequence,
    Solution,
    default_block_type,
)


def choose_demand_ids(instance, count: int) -> list[int]:
    """Choose deterministic demands with individually feasible direct blocks.

    The first prototype needs a benchmark-feasible seed. We therefore keep
    demands whose direct shortest-path block already satisfies minimum volume
    and physical link-capacity checks, while keeping origins distinct.
    """

    if count <= 0:
        raise ValueError("count must be positive")

    router = DijkstraRouter(instance)
    selected: list[int] = []
    used_origins: set[int] = set()

    for demand_id in sorted(instance.demands):
        demand = instance.demands[demand_id]
        if demand.origin_yard_id in used_origins:
            continue

        route = router.shortest_path(demand.origin_yard_id, demand.dest_yard_id)
        if route is None:
            continue

        volume = demand.effective_volume(instance.settings)
        if route.distance < 100:
            minimum = instance.settings.min_block_vol_short
        elif route.distance <= 500:
            minimum = instance.settings.min_block_vol_medium
        else:
            minimum = instance.settings.min_block_vol_long
        if volume + 1e-6 < minimum:
            continue

        if any(
            volume > instance.links[link_id].capacity
            for link_id in route.link_ids
        ):
            continue

        selected.append(demand_id)
        used_origins.add(demand.origin_yard_id)
        if len(selected) == count:
            return selected

    raise ValueError(
        f"could only find {len(selected)} individually feasible demands with "
        f"distinct origins; requested {count}"
    )


def make_slice(base, demand_ids: list[int]):
    demands = {demand_id: base.demands[demand_id] for demand_id in demand_ids}
    from jev_rbp.problem import RBPInstance

    return RBPInstance(
        nodes=base.nodes,
        links=base.links,
        demands=demands,
        settings=base.settings,
    )


def build_direct_seed(instance, router: DijkstraRouter) -> Solution:
    """Build one direct block per selected demand.

    This is intentionally a simple experimental seed, not the official
    competition greedy solver.
    """

    solution = Solution()
    for demand_id in sorted(instance.demands):
        demand = instance.demands[demand_id]
        route = router.shortest_path(demand.origin_yard_id, demand.dest_yard_id)
        if route is None:
            raise ValueError(
                f"demand {demand_id} has no physical route "
                f"{demand.origin_yard_id}->{demand.dest_yard_id}"
            )

        block = Block(
            block_id=demand_id,
            from_yard_id=demand.origin_yard_id,
            to_yard_id=demand.dest_yard_id,
            block_type=default_block_type(demand.commodity_type),
            volume=demand.effective_volume(instance.settings),
        )
        solution.blocks[demand_id] = block
        solution.sequences[demand_id] = BlockingSequence(
            demand_id=demand_id,
            block_ids=(demand_id,),
            volume=demand.effective_volume(instance.settings),
        )
        solution.routes[demand_id] = BlockRoute(
            block_id=demand_id,
            node_ids=route.node_ids,
            link_ids=route.link_ids,
        )

    return solution


def build_case(instance, instance_id: str) -> tuple[ExperimentCase, DijkstraRouter]:
    router = DijkstraRouter(instance)
    context = MoveContext(instance=instance, router=router)
    generator = RBPMoveGenerator(
        context,
        candidate_yards={
            yard_id
            for demand in instance.demands.values()
            for yard_id in (demand.origin_yard_id, demand.dest_yard_id)
        },
    )
    return (
        ExperimentCase(
            instance_id=instance_id,
            instance=instance,
            initial_solution=build_direct_seed(instance, router),
            generator=generator,
            evaluator=ExactRBPMoveEvaluator(context),
            applier=RBPMoveApplier(context),
            validator=RBPMoveValidator(context),
        ),
        router,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/ras2026-v2.1/l1"),
        help="prepared RAS v2.1 L1 directory",
    )
    parser.add_argument(
        "--demands",
        type=int,
        default=12,
        help="total selected demands, split into train/test slices",
    )
    parser.add_argument(
        "--test-fraction",
        type=float,
        default=1 / 3,
        help="fraction of selected demands reserved for the test slice",
    )
    parser.add_argument(
        "--dataset-iterations",
        type=int,
        default=1,
        help="reference iterations used for offline JEV label collection",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="search iterations for each selector run",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/l1-first-experiment"),
        help="directory for experiment outputs",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0.0 < args.test_fraction < 1.0:
        raise ValueError("--test-fraction must be between 0 and 1")

    base = load_instance(args.data)
    selected = choose_demand_ids(base, args.demands)
    test_count = max(1, round(len(selected) * args.test_fraction))
    train_ids = selected[:-test_count]
    test_ids = selected[-test_count:]

    train_instance = make_slice(base, train_ids)
    test_instance = make_slice(base, test_ids)
    train_case, train_router = build_case(train_instance, "l1-demand-train")
    test_case, test_router = build_case(test_instance, "l1-demand-test")

    train_yards = {
        y
        for demand in train_instance.demands.values()
        for y in (demand.origin_yard_id, demand.dest_yard_id)
    }
    test_yards = {
        y
        for demand in test_instance.demands.values()
        for y in (demand.origin_yard_id, demand.dest_yard_id)
    }
    print(
        f"L1 slice: {len(train_ids)} train demands / {len(test_ids)} test demands; "
        f"train yards={len(train_yards)}, test yards={len(test_yards)}"
    )

    train_rows = collect_jev_dataset(
        train_case.initial_solution,
        train_case.generator,
        train_case.evaluator,
        train_case.applier,
        train_instance,
        train_router,
        instance_id=train_case.instance_id,
        max_iterations=args.dataset_iterations,
        feature_extractor=make_rbp_feature_extractor(train_instance, train_router),
    )
    if not train_rows:
        raise RuntimeError("JEV training dataset is empty")

    model = fit_linear_jev(train_rows)

    test_rows = collect_jev_dataset(
        test_case.initial_solution,
        test_case.generator,
        test_case.evaluator,
        test_case.applier,
        test_instance,
        test_router,
        instance_id=test_case.instance_id,
        max_iterations=1,
        feature_extractor=make_rbp_feature_extractor(test_instance, test_router),
    )
    ranking = {
        str(k): asdict(
            grouped_ranking_metrics(
                test_rows,
                lambda row: model.predict_features(row.features),
                k=k,
            )
        )
        for k in (1, 5, 10)
    }

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(train_rows, output / "train.jsonl")
    (output / "model.json").write_text(
        json.dumps(asdict(model), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output / "ranking.json").write_text(
        json.dumps(ranking, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output / "config.json").write_text(
        json.dumps(
            {
                "data": str(args.data),
                "selected_demand_ids": selected,
                "train_demand_ids": train_ids,
                "test_demand_ids": test_ids,
                "dataset_iterations": args.dataset_iterations,
                "max_iterations": args.max_iterations,
                "note": "train/test are demand slices of one L1 physical network",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    def jev_factory(case: ExperimentCase):
        router = DijkstraRouter(case.instance)
        return LinearJEVSelector(
            model,
            make_rbp_feature_extractor(case.instance, router),
        )

    selectors = {
        "identity": lambda _: IdentitySelector(),
        "random": lambda case: RandomSelector(
            seed=0 if case.instance_id.endswith("train") else 1
        ),
        "rbp-greedy": lambda case: RBPGreedySelector(
            case.instance, DijkstraRouter(case.instance)
        ),
        "linear-jev": jev_factory,
    }

    all_results = []
    for budget in (1, 5, 10):
        all_results.extend(
            run_selector_suite(
                [test_case],
                selectors,
                exact_evaluation_budget=budget,
                max_iterations=args.max_iterations,
            )
        )

    with (output / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(all_results[0]).keys()))
        writer.writeheader()
        for result in all_results:
            writer.writerow(asdict(result))

    (output / "results.json").write_text(
        json.dumps([asdict(result) for result in all_results], indent=2),
        encoding="utf-8",
    )

    print(f"training rows: {len(train_rows)}")
    print(f"test ranking rows: {len(test_rows)}")
    for k, metrics in ranking.items():
        print(
            f"linear-jev ranking K={k}: "
            f"pools={metrics['pools']} "
            f"top_k_hit_rate={metrics['top_k_hit_rate']:.3f} "
            f"mean_regret={metrics['mean_regret']:.6f}"
        )
    print(f"results: {output / 'results.csv'}")
    for result in all_results:
        print(
            f"{result.selector:12s} K={result.exact_evaluation_budget:<2} "
            f"evals={result.exact_evaluations:<4} "
            f"cost={result.final_operating_cost:.2f} "
            f"stress={result.final_stress_score:.2f} "
            f"feasible={result.benchmark_feasible}"
        )


if __name__ == "__main__":
    main()
