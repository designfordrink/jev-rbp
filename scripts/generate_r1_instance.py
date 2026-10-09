#!/usr/bin/env python3
"""Deterministic first-pass R1-C 8-yard / 50-demand instance generator.

This is a constrained *candidate* generator, not an acceptance oracle. Every
candidate is run through the design checker; a failing candidate is not frozen.
Dynamic search phenomena P1-P7 still require the later solver audit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

GENERATOR_VERSION = "r1c-generator-0.1.0"

NODE_FIELDS = [
    "node_id", "node_type", "name", "x_coord", "y_coord", "yard_type",
    "yard_level", "railroad_id", "num_tracks", "handling_capacity",
    "handling_cost", "is_interchange", "allowed_commodities",
    "allowed_traversal", "datasource",
]
LINK_FIELDS = [
    "link_id", "from_node_id", "to_node_id", "length", "capacity",
    "railroad_id", "free_speed", "tracks", "geometry",
]
DEMAND_FIELDS = ["demand_id", "origin_yard_id", "dest_yard_id", "volume", "commodity_type", "block_type"]
SETTING_FIELDS = ["parameter", "value"]

YARDS = [
    (1, "A", "hump", 3, 9000, 1.0, "BNSF", False),
    (2, "B", "hump", 5, 12000, 1.4, "BNSF", True),
    (3, "C", "flat", 2, 6500, 1.8, "BNSF", False),
    (4, "D", "flat", 4, 10000, 2.2, "CSX", True),
    (5, "E", "hump", 6, 14000, 1.2, "CSX", False),
    (6, "F", "flat", 3, 7500, 2.7, "CSX", False),
    (7, "G", "hump", 5, 11000, 1.6, "UP", True),
    (8, "H", "flat", 2, 5500, 3.0, "UP", True),
]
EDGES = [
    (1, 2, 70), (2, 3, 145), (3, 4, 160), (4, 5, 175),
    (5, 6, 150), (6, 7, 165), (7, 8, 180), (8, 1, 240),
    (2, 7, 300), (3, 6, 285), (4, 8, 260),
]
DEMAND_COUNTS = [
    ("Merchandise", "Manifest", 20),
    ("Coal", "Bulk", 10),
    ("Grain", "Bulk", 10),
    ("Intermodal", "Intermodal", 5),
    ("Automobile", "Multilevel", 5),
]
SETTINGS = [
    ("min_block_vol_short(<100mi)", 350),
    ("min_block_vol_med(100-500mi)", 700),
    ("min_block_vol_long(>500mi)", 1050),
    ("max_circuitous_ratio", 1.3),
    ("operating_cycle", 70),
    ("block_fixed_cost", 2500),
    ("transport_cost_coefficient", 1.0),
    ("interchange_cost", 100),
    ("stress_penalty_m", 5),
    ("demand_multiplier", 1.0),
]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_candidate(seed: int, output: Path) -> dict:
    rng = random.Random(seed)
    output.mkdir(parents=True, exist_ok=True)
    nodes = []
    for node_id, name, yard_type, tracks, handling, cost, railroad, interchange in YARDS:
        nodes.append({
            "node_id": node_id, "node_type": "yard", "name": name,
            "x_coord": (node_id - 1) * 100.0, "y_coord": 0,
            "yard_type": yard_type, "yard_level": 1, "railroad_id": railroad,
            "num_tracks": tracks, "handling_capacity": handling,
            "handling_cost": cost, "is_interchange": str(interchange).upper(),
            "allowed_commodities": "Merchandise|Coal|Grain|Intermodal|Automobile",
            "allowed_traversal": "ALL", "datasource": "R1-C controlled synthetic",
        })
    links = []
    for link_id, (u, v, length) in enumerate(EDGES, start=1):
        links.append({
            "link_id": link_id, "from_node_id": u, "to_node_id": v,
            "length": length, "capacity": [1800, 2400, 3200][(link_id + seed) % 3],
            "railroad_id": YARDS[u - 1][6], "free_speed": 40,
            "tracks": 1, "geometry": "",
        })

    # Spread O-D pairs over the graph. The seed controls demand ordering/volume,
    # not topology or type counts, making candidates reproducible and comparable.
    pairs = [(u, v) for u in range(1, 9) for v in range(1, 9) if u != v]
    rng.shuffle(pairs)
    # Use both directions of selected pairs; no demand has identical endpoints.
    demand_specs = []
    for commodity, block_type, count in DEMAND_COUNTS:
        for _ in range(count):
            demand_specs.append((commodity, block_type))
    rng.shuffle(demand_specs)
    demands = []
    for demand_id, (commodity, block_type) in enumerate(demand_specs, start=1):
        origin, destination = pairs[(demand_id - 1) % len(pairs)]
        if commodity in {"Intermodal", "Automobile"}:
            volume = rng.choice([1200, 1350, 1500, 1650])
        else:
            volume = rng.choice([250, 400, 550, 750, 900, 1100, 1300])
        demands.append({
            "demand_id": demand_id, "origin_yard_id": origin,
            "dest_yard_id": destination, "volume": volume,
            "commodity_type": commodity, "block_type": commodity,
        })
    # Checker uses block_type as the demand/commodity label; preserve block_type
    # as the canonical type and commodity_type as the same compatibility value.
    for row in demands:
        row["block_type"] = row["commodity_type"]

    write_csv(output / "nodes.csv", NODE_FIELDS, nodes)
    write_csv(output / "links.csv", LINK_FIELDS, links)
    write_csv(output / "demands.csv", DEMAND_FIELDS, demands)
    write_csv(output / "setting.csv", SETTING_FIELDS, [
        {"parameter": key, "value": value} for key, value in SETTINGS
    ])

    hashes = {}
    for name in ("nodes.csv", "links.csv", "demands.csv", "setting.csv"):
        hashes[name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    manifest = {
        "benchmark_id": "R1-C8x50-A",
        "generator": GENERATOR_VERSION,
        "seed": seed,
        "parameters": {"yards": 8, "demands": 50, "topology": "fixed 8-node ring plus 3 chords"},
        "source_commit": "record the git commit used to run this generator",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "schema_version": "RBP/RAS v2.1 compatible CSV; design-checker schema",
        "sha256": hashes,
        "scientific_status": "candidate; dynamic P1-P7 and solver feasibility not yet established",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--output", type=Path, default=Path("data/R1-C8x50-A"))
    parser.add_argument("--checker", type=Path, default=Path("scripts/check_r1_instance.py"))
    args = parser.parse_args()

    manifest = build_candidate(args.seed, args.output)
    print(f"Generated candidate {manifest['benchmark_id']} at {args.output} (seed={args.seed}).")
    print("Running static design checker; dynamic P1-P7 remain unevaluated.")
    result = subprocess.run(
        [sys.executable, str(args.checker), str(args.output), "--json"],
        check=False, text=True, capture_output=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        print("Candidate rejected by static checker; do not freeze or use for JEV claims.", file=sys.stderr)
        return result.returncode
    print("Static gate passed. This is not yet a frozen/accepted benchmark: run solver audit and P1-P7.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
