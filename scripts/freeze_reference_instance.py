#!/usr/bin/env python3
"""CLI wrapper for freezing Nicolas Bridelance's R1 reference instance."""

from __future__ import annotations

import argparse
from pathlib import Path

from jev_rbp.reference_freeze import freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/reference/reconstruction/8x50"),
    )
    args = parser.parse_args()

    manifest = freeze(args.source, args.output)
    counts = manifest["counts"]
    print(f"Frozen R1 instance: {args.output.resolve()}")
    print(f"  yards       : {counts['yards']}")
    print(f"  commodities : {counts['commodities']}")
    print(f"  nodes       : {counts['total_nodes']}")
    print(f"  manifest    : {args.output.resolve() / 'manifest.json'}")


if __name__ == "__main__":
    main()
