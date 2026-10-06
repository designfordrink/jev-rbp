from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.freeze_reference_instance import freeze


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def _make_source(root: Path, yards: int = 8, commodities: int = 50) -> None:
    _write_csv(
        root / "nodes.csv",
        "node_id,node_type",
        [f"y{i},yard" for i in range(yards)],
    )
    _write_csv(
        root / "links.csv",
        "link_id,from,to",
        ["l1,y0,y1"],
    )
    _write_csv(
        root / "demands.csv",
        "demand_id,origin,destination",
        [f"d{i},y0,y1" for i in range(commodities)],
    )
    _write_csv(
        root / "setting.csv",
        "key,value",
        ["example,value"],
    )


def test_freeze_copies_bytes_and_records_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    _make_source(source)

    freeze(source, output)

    for name in ("nodes.csv", "links.csv", "demands.csv", "setting.csv"):
        assert (output / name).read_bytes() == (source / name).read_bytes()

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["yards"] == 8
    assert manifest["commodity_count"] == 50
    assert set(manifest["files"]) == {
        "nodes.csv",
        "links.csv",
        "demands.csv",
        "setting.csv",
    }
    for name in manifest["files"]:
        assert len(manifest["files"][name]["sha256"]) == 64


@pytest.mark.parametrize(
    ("yards", "commodities", "message"),
    [
        (7, 50, "expected 8 yard rows"),
        (8, 49, "expected 50 commodity rows"),
    ],
)
def test_freeze_rejects_wrong_shape(
    tmp_path: Path, yards: int, commodities: int, message: str
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    _make_source(source, yards=yards, commodities=commodities)

    with pytest.raises(SystemExit, match=message):
        freeze(source, output)
