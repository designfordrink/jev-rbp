#!/usr/bin/env python3
"""Run the archived Nicolas Bridelance reference solvers."""

from __future__ import annotations

import argparse
import json
import sys
import time
import types
from pathlib import Path


def _install_reference_namespace(repo_root: Path) -> None:
    """Expose data/reference/archive as the historical src package."""
    archive = repo_root / "data" / "reference" / "archive"
    if not archive.exists():
        raise FileNotFoundError(f"Reference archive not found: {archive}")

    namespace = types.ModuleType("src")
    namespace.__path__ = [str(archive)]
    namespace.__package__ = "src"
    sys.modules["src"] = namespace


def _solution_summary(solution) -> dict:
    return {
        "feasible": bool(solution.is_feasible),
        "unrouted": list(getattr(solution, "unrouted", [])),
        "blocks": len(getattr(solution, "blocks", [])),
        "sequences": len(getattr(solution, "sequences", [])),
        "objective": getattr(solution, "obj_value", None),
        "solve_time_s": getattr(solution, "solve_time", None),
        "iterations": getattr(solution, "n_iterations", None),
        "improvements": getattr(solution, "improvements", None),
        "mip_gap": getattr(solution, "mip_gap", None),
        "lower_bound": getattr(solution, "lower_bound", None),
    }


def _write_solution(output_dir: Path, name: str, solution, network) -> None:
    path = output_dir / f"{name}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            solution.to_solution_dict(network),
            handle,
            ensure_ascii=False,
            indent=2,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/reference-reconstruction"),
    )
    parser.add_argument("--vlns-time-limit", type=float, default=300.0)
    parser.add_argument("--vlns-max-iterations", type=int, default=200)
    parser.add_argument("--mip-time-limit", type=float, default=300.0)
    parser.add_argument("--mip-gap", type=float, default=0.001)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _install_reference_namespace(repo_root)

    from src.data_loader import load_rail_network
    from src.evaluator import evaluate
    from src.solvers.greedy import solve_greedy
    from src.solvers.mip import solve_mip
    from src.solvers.vlns import solve_vlns
    from src.validator import validate

    data_dir = args.data_dir.resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    network = load_rail_network(data_dir)

    manifest = {
        "data_dir": str(data_dir),
        "yards": int(len(network.yards_df)),
        "commodities": int(len(network.demands_df)),
        "solvers": {},
    }

    greedy = solve_greedy(network)
    greedy_dict = greedy.to_solution_dict(network)
    greedy_eval = evaluate(network, greedy_dict)
    greedy_validation = validate(network, greedy_dict)
    _write_solution(output_dir, "greedy", greedy, network)
    manifest["solvers"]["greedy"] = {
        **_solution_summary(greedy),
        "objective_evaluator": greedy_eval.total_cost,
        "validation_feasible": bool(greedy_validation.is_feasible),
        "validation_violations": list(greedy_validation.violations),
    }

    t0 = time.perf_counter()
    vlns = solve_vlns(
        network,
        initial_solution=greedy,
        max_iterations=args.vlns_max_iterations,
        time_limit=args.vlns_time_limit,
        verbose=False,
    )
    manifest["solvers"]["vlns_wall_time_s"] = time.perf_counter() - t0
    vlns_dict = vlns.to_solution_dict(network)
    vlns_eval = evaluate(network, vlns_dict)
    vlns_validation = validate(network, vlns_dict)
    _write_solution(output_dir, "vlns", vlns, network)
    manifest["solvers"]["vlns"] = {
        **_solution_summary(vlns),
        "objective_evaluator": vlns_eval.total_cost,
        "validation_feasible": bool(vlns_validation.is_feasible),
        "validation_violations": list(vlns_validation.violations),
    }

    t0 = time.perf_counter()
    mip = solve_mip(
        network,
        warm_start=greedy,
        time_limit=args.mip_time_limit,
        mip_gap=args.mip_gap,
        verbose=False,
    )
    manifest["solvers"]["mip_wall_time_s"] = time.perf_counter() - t0
    mip_dict = mip.to_solution_dict(network)
    mip_eval = evaluate(network, mip_dict)
    mip_validation = validate(network, mip_dict)
    _write_solution(output_dir, "mip", mip, network)
    manifest["solvers"]["mip"] = {
        **_solution_summary(mip),
        "objective_evaluator": mip_eval.total_cost,
        "validation_feasible": bool(mip_validation.is_feasible),
        "validation_violations": list(mip_validation.violations),
    }

    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
