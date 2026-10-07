"""Reusable tooling for freezing the R1 Nicolas reference instance."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

REQUIRED_FILES = ("nodes.csv", "links.csv", "demands.csv", "setting.csv")
EXPECTED_YARDS = 8
EXPECTED_COMMODITIES = 50


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_source(source: Path) -> dict[str, int]:
    missing = [name for name in REQUIRED_FILES if not (source / name).is_file()]
    if missing:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")

    nodes = csv_rows(source / "nodes.csv")
    demands = csv_rows(source / "demands.csv")
    yards = [
        row for row in nodes
        if str(row.get("node_type", "")).strip().lower() == "yard"
    ]

    if len(yards) != EXPECTED_YARDS:
        raise SystemExit(
            f"R1 guard failed: expected 8 yard rows, found {len(yards)} "
            f"(total nodes={len(nodes)})."
        )
    if len(demands) != EXPECTED_COMMODITIES:
        raise SystemExit(
            f"R1 guard failed: expected 50 commodity rows, found {len(demands)}."
        )

    return {
        "total_nodes": len(nodes),
        "yards": len(yards),
        "commodities": len(demands),
    }


def freeze(source: Path, output: Path) -> dict:
    """Copy a validated R1 source byte-for-byte and write a hash manifest."""
    source = Path(source).resolve()
    output = Path(output).resolve()
    counts = validate_source(source)

    output.mkdir(parents=True, exist_ok=True)
    if any(
        (output / name).exists()
        for name in (*REQUIRED_FILES, "manifest.json")
    ):
        raise SystemExit(
            f"Refusing to overwrite an existing freeze directory: {output}"
        )

    manifest = {
        "reference": "Nicolas Bridelance toy instance",
        "target": "8 yards / 50 commodities",
        "source_directory": str(source),
        "counts": counts,
        "files": {},
    }

    for name in REQUIRED_FILES:
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
    return manifest
