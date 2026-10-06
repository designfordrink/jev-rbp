#!/usr/bin/env python3
"""Freeze Nicolas Bridelance's 8-yard / 50-commodity reference instance.

The source directory must contain the four files expected by the archived
reference loader: nodes.csv, links.csv, demands.csv, setting.csv.

This script deliberately performs no normalization or transformation. It
copies the reference files byte-for-byte and records SHA-256 hashes so that
the R1 instance is an immutable provenance point.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


EXPECTED = {
    "nodes.csv": 8,       # expected number of rows with node_type == yard
    "demands.csv": 50,    # expected number of commodity rows
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_source(source: Path) -> dict:
    required = ["nodes.csv", "links.csv", "demands.csv", "setting.csv"]
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")

    nodes = csv_rows(source / "nodes.csv")
    demands = csv_rows(source / "demands.csv")

    yards = [r for r in nodes if str(r.get("node_type", "")).strip().lower() == "yard"]

    if len(yards) != EXPECTED["nodes.csv"]:
        raise SystemExit(
            f"R1 guard failed: expected 8 yard rows, found {len(yards)} "
            f"(total nodes={len(nodes)})."
        )

    if len(demands) != EXPECTED["demands.csv"]:
        raise SystemExit(
            f"R1 guard failed: expected 50 commodity rows, found {len(demands)}."
        )

    return {
        "total_nodes": len(nodes),
        "yards": len(yards),
        "commodities": len(demands),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reference/reconstruction/8x50"),
    )
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()

    counts = validate_source(source)

    output.mkdir(parents=True, exist_ok=True)

    files = ["nodes.csv", "links.csv", "demands.csv", "setting.csv"]
    manifest = {
        "reference": "Nicolas Bridelance toy instance",
        "target": "8 yards / 50 commodities",
        "source_directory": str(source),
        "counts": counts,
        "files": {},
    }

    for name in files:
        src = source / name
        dst = output / name
        shutil.copy2(src, dst)
        manifest["files"][name] = {
            "sha256": sha256(dst),
            "bytes": dst.stat().st_size,
        }

    manifest["manifest_sha256"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Frozen R1 instance: {output}")
    print(f"  yards       : {counts['yards']}")
    print(f"  commodities : {counts['commodities']}")
    print(f"  nodes       : {counts['total_nodes']}")
    print(f"  manifest    : {output / 'manifest.json'}")


if __name__ == "__main__":
    main()
