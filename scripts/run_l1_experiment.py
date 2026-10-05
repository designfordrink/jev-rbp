#!/usr/bin/env python3
"""Run the second controlled RAS L1 experiment.

This experiment uses several demand-pattern cases cut from the same public L1
physical network. They are deliberately called *cases*, not independent
benchmark instances: sharing the physical network limits the generalization
claim. The same candidate generator, exact evaluator, validator and
acceptance rule are used for every selector.

Vanilla VLNS is represented by selector=None in the canonical search engine.
It is expensive because it evaluates the complete candidate pool; use
--include-vanilla when a full baseline run is desired.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

from jev_rbp.dataset import collect_jev_dataset, make_rbp_feature_extractor, write_jsonl
from jev_rbp.experiment_runner import ExperimentCase, run_selector_suite
from jev_rbp.experiments import grouped_ranking_metrics
from jev_rbp.io import load_instance
from jev_rbp.jev import LinearJEVSelector, fit_linear_jev
from jev_rbp.moves import (
    ExactRBPMoveEvaluator,
    MoveContext,
    RBPMoveApplier,
    RBPMoveGenerator,
    RBPMoveValidator,
)
from jev_rbp.problem import (
    Block,
    BlockRoute,
    BlockingSequence,
    RBPInstance,
    Solution,
    default_block_type,
)
from jev_rbp.rbp_selectors import RBPGreedySelector
from jev_rbp.routing import DijkstraRouter
from jev_rbp.selectors import IdentitySelector, RandomSelector


def choose_demand_ids(instance, count: int) -> list[int]:
    """Choose direct-seed-safe demands with distinct origins."""

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
        if any(volume > instance.links[link_id].capacity for link_id in route.link_ids):
            continue
        selected.append(demand_id)
        used_origins.add(demand.origin_yard_id)
        if len(selected) == count:
            return selected

    raise ValueError(f"could only find {len(selected)} safe demands; requested {count}")


def make_slice(base: RBPInstance, demand_ids: list[int]) -> RBPInstance:
    return RBPInstance(
        nodes=base.nodes,
        links=base.links,
        demands={demand_id: base.demands[demand_id] for demand_id in demand_ids},
        settings=base.settings,
    )


def build_direct_seed(instance: RBPInstance, router: DijkstraRouter) -> Solution:
    solution = Solution()
    for demand_id in sorted(instance.demands):
        demand = instance.demands[demand_id]
        route = router.shortest_path(demand.origin_yard_id, demand.dest_yard_id)
        if route is None:
            raise ValueError(f"demand {demand_id} has no physical route")
        block_id = demand_id * 100 + 1
        solution.blocks[block_id] = Block(
            block_id=block_id,
            from_yard_id=demand.origin_yard_id,
            to_yard_id=demand.dest_yard_id,
            block_type=default_block_type(demand.commodity_type),
            volume=demand.effective_volume(instance.settings),
        )
        solution.routes[block_id] = BlockRoute(
            block_id=block_id,
            node_ids=route.node_ids,
            link_ids=route.link_ids,
        )
        solution.sequences[demand_id] = BlockingSequence(
            demand_id=demand_id,
            block_ids=(block_id,),
            volume=demand.effective_volume(instance.settings),
        )
    return solution


def build_case(instance: RBPInstance, instance_id: str) -> tuple[ExperimentCase, DijkstraRouter]:
    router = DijkstraRouter(instance)
    context = MoveContext(instance=instance, router=router)
    active_yards = {
        yard_id
        for demand in instance.demands.values()
        for yard_id in (demand.origin_yard_id, demand.dest_yard_id)
    }
    generator = RBPMoveGenerator(context, candidate_yards=active_yards)
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
    parser.add_argument("--data", type=Path, default=Path("data/ras2026-v2.1/l1"))
    parser.add_argument("--demands", type=int, default=20)
    parser.add_argument("--case-size", type=int, default=4)
    parser.add_argument("--train-cases", type=int, default=3)
    parser.add_argument("--dataset-iterations", type=int, default=2)
    parser.add_argument("--max-iterations", type=int, default=2)
    parser.add_argument("--include-vanilla", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/l1-experiment-v2")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.demands < args.case_size * (args.train_cases + 1):
        raise ValueError("--demands must cover train cases plus at least one test case")

    base = load_instance(args.data)
    selected = choose_demand_ids(base, args.demands)
    groups = [
        selected[i : i + args.case_size]
        for i in range(0, len(selected), args.case_size)
    ]
    cases = []
    routers = {}
    for index, demand_ids in enumerate(groups):
        case, router = build_case(
            make_slice(base, demand_ids),
            f"l1-case-{index:02d}",
        )
        cases.append(case)
        routers[case.instance_id] = router

    train_cases = cases[: args.train_cases]
    test_cases = cases[args.train_cases :]
    if not test_cases:
        raise ValueError("no test cases remain")

    train_rows = []
    for case in train_cases:
        train_rows.extend(
            collect_jev_dataset(
                case.initial_solution,
                case.generator,
                case.evaluator,
                case.applier,
                case.instance,
                routers[case.instance_id],
                instance_id=case.instance_id,
                max_iterations=args.dataset_iterations,
                feature_extractor=make_rbp_feature_extractor(
                    case.instance, routers[case.instance_id]
                ),
            )
        )
    if not train_rows:
        raise RuntimeError("JEV training dataset is empty")
    model = fit_linear_jev(train_rows)

    test_rows = []
    for case in test_cases:
        test_rows.extend(
            collect_jev_dataset(
                case.initial_solution,
                case.generator,
                case.evaluator,
                case.applier,
                case.instance,
                routers[case.instance_id],
                instance_id=case.instance_id,
                max_iterations=args.dataset_iterations,
                feature_extractor=make_rbp_feature_extractor(
                    case.instance, routers[case.instance_id]
                ),
            )
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

    def jev_factory(case: ExperimentCase):
        return LinearJEVSelector(
            model,
            make_rbp_feature_extractor(case.instance, routers[case.instance_id]),
        )

    selectors = {
        "identity": lambda _: IdentitySelector(),
        "random": lambda case: RandomSelector(
            seed=1000 + int(case.instance_id.rsplit("-", 1)[1])
        ),
        "rbp-greedy": lambda case: RBPGreedySelector(
            case.instance, routers[case.instance_id]
        ),
        "linear-jev": jev_factory,
    }
    if args.include_vanilla:
        selectors["vanilla-vlns"] = lambda _: None

    results = []
    for budget in (1, 5, 10):
        results.extend(
            run_selector_suite(
                test_cases,
                selectors,
                exact_evaluation_budget=budget,
                max_iterations=args.max_iterations,
            )
        )

    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(train_rows, output / "train.jsonl")
    write_jsonl(test_rows, output / "test.jsonl")
    (output / "model.json").write_text(
        json.dumps(asdict(model), indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "ranking.json").write_text(
        json.dumps(ranking, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output / "config.json").write_text(
        json.dumps(
            {
                "selected_demand_ids": selected,
                "case_demand_ids": [sorted(case.instance.demands) for case in cases],
                "train_case_ids": [case.instance_id for case in train_cases],
                "test_case_ids": [case.instance_id for case in test_cases],
                "dataset_iterations": args.dataset_iterations,
                "max_iterations": args.max_iterations,
                "exact_budgets": [1, 5, 10],
                "include_vanilla": args.include_vanilla,
                "important_note": (
                    "Cases share the same L1 physical network and are not "
                    "independent benchmark instances."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    if results:
        with (output / "results.csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(asdict(results[0]).keys()))
            writer.writeheader()
            for result in results:
                writer.writerow(asdict(result))
        (output / "results.json").write_text(
            json.dumps([asdict(result) for result in results], indent=2),
            encoding="utf-8",
        )

    print(
        f"cases={len(cases)} train={len(train_cases)} test={len(test_cases)} "
        f"train_rows={len(train_rows)} test_rows={len(test_rows)}"
    )
    for k, metrics in ranking.items():
        print(
            f"JEV ranking K={k}: pools={metrics['pools']} "
            f"top_k_hit_rate={metrics['top_k_hit_rate']:.3f} "
            f"mean_regret={metrics['mean_regret']:.6f}"
        )
    for result in results:
        print(
            f"{result.instance_id} {result.selector:12s} "
            f"K={result.exact_evaluation_budget!s:>4} "
            f"evals={result.exact_evaluations:<5} "
            f"cost={result.final_operating_cost:.2f} "
            f"stress={result.final_stress_score:.2f} "
            f"feasible={result.benchmark_feasible}"
        )


if __name__ == "__main__":
    main()
