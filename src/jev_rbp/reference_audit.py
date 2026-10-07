"""Audit downloaded Kaggle dataset candidates for the R1 8x50 instance."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
import zipfile
from pathlib import Path

from jev_rbp.reference_freeze import REQUIRED_FILES, validate_source


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_candidate(root: Path) -> Path | None:
    for directory in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
        if all((directory / name).is_file() for name in REQUIRED_FILES):
            return directory
    return None


def inspect_path(path: Path) -> dict:
    path = path.resolve()
    temp: tempfile.TemporaryDirectory[str] | None = None
    root = path

    if path.is_file() and path.suffix.lower() in {".zip", ".tar", ".gz", ".tgz"}:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                archive.extractall(root)
        else:
            with tarfile.open(path, "r:*") as archive:
                archive.extractall(root)

    candidate = find_candidate(root)
    result = {
        "source": str(path),
        "candidate": str(candidate) if candidate else None,
        "is_r1_candidate": False,
        "files": {},
    }

    if candidate is None:
        result["reason"] = "required four CSV files not found together"
    else:
        try:
            counts = validate_source(candidate)
            result["is_r1_candidate"] = True
            result["counts"] = counts
            for name in REQUIRED_FILES:
                file_path = candidate / name
                result["files"][name] = {
                    "bytes": file_path.stat().st_size,
                    "sha256": sha256(file_path),
                }
        except SystemExit as exc:
            result["reason"] = str(exc)

    if temp is not None:
        temp.cleanup()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inspect_path(args.path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Source: {result['source']}")
        print(f"Candidate: {result['candidate'] or 'not found'}")
        print(f"R1 candidate: {'YES' if result['is_r1_candidate'] else 'NO'}")
        if result.get("reason"):
            print(f"Reason: {result['reason']}")
        if result.get("counts"):
            print(f"Counts: {result['counts']}")
        for name, info in result["files"].items():
            print(f"{name}: {info['bytes']} bytes, sha256={info['sha256']}")


if __name__ == "__main__":
    main()
