#!/usr/bin/env python3
"""Download the public RAS 2026 v2.1 L1 inputs for local experiments.

The benchmark repository keeps large link data compressed. This script downloads
only the L1 files needed by the clean-room JEV-RBP loader and verifies the
published SHA-256 checksum of link.csv.zip.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://raw.githubusercontent.com/asu-trans-ai-lab/RAS2026-PSC/v2.1"
LINK_SHA256 = "db9a6f2900e5011d632567882f91fbb7a42f19a40e2450fd0c2e8733a4d62e37"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"download {url}")
    with urllib.request.urlopen(url) as response, destination.open("wb") as fh:
        shutil.copyfileobj(response, fh)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/ras2026-v2.1/l1"),
        help="directory for the local L1 experiment data",
    )
    args = parser.parse_args()
    root = args.output

    for name in ("node.csv", "demand.csv", "setting.csv"):
        download(f"{BASE}/datasets/l1/{name}", root / name)

    archive = root / "link.csv.zip"
    download(f"{BASE}/datasets/l1/link.csv.zip", archive)

    actual = sha256(archive)
    if actual != LINK_SHA256:
        raise RuntimeError(
            f"link.csv.zip checksum mismatch: expected {LINK_SHA256}, got {actual}"
        )

    with zipfile.ZipFile(archive) as zf:
        members = [name for name in zf.namelist() if name.endswith("link.csv")]
        if len(members) != 1:
            raise RuntimeError(f"expected one link.csv in archive, found {members}")
        with zf.open(members[0]) as source, (root / "link.csv").open("wb") as target:
            shutil.copyfileobj(source, target)

    print(f"prepared {root}")
    print("source: RAS2026-PSC v2.1")
    print(f"link.csv.zip sha256: {actual}")


if __name__ == "__main__":
    main()
