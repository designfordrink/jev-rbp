from __future__ import annotations

import zipfile
from pathlib import Path

from jev_rbp.reference_audit import inspect_path


def _make_source(root: Path, yards: int = 8, commodities: int = 50) -> None:
    (root / "nodes.csv").write_text(
        "node_id,node_type\n" + "\n".join(f"y{i},yard" for i in range(yards)) + "\n",
        encoding="utf-8",
    )
    (root / "links.csv").write_text("link_id,from,to\nl1,y0,y1\n", encoding="utf-8")
    (root / "demands.csv").write_text(
        "demand_id,origin,destination\n"
        + "\n".join(f"d{i},y0,y1" for i in range(commodities))
        + "\n",
        encoding="utf-8",
    )
    (root / "setting.csv").write_text("key,value\nexample,value\n", encoding="utf-8")


def test_audit_directory(tmp_path: Path) -> None:
    source = tmp_path / "candidate"
    source.mkdir()
    _make_source(source)

    result = inspect_path(source)

    assert result["is_r1_candidate"] is True
    assert result["counts"] == {"total_nodes": 8, "yards": 8, "commodities": 50}
    assert len(result["files"]["nodes.csv"]["sha256"]) == 64


def test_audit_zip(tmp_path: Path) -> None:
    source = tmp_path / "candidate"
    source.mkdir()
    _make_source(source)
    archive = tmp_path / "candidate.zip"

    with zipfile.ZipFile(archive, "w") as zf:
        for file in source.iterdir():
            zf.write(file, file.name)

    result = inspect_path(archive)

    assert result["is_r1_candidate"] is True


def test_audit_rejects_wrong_shape(tmp_path: Path) -> None:
    source = tmp_path / "candidate"
    source.mkdir()
    _make_source(source, commodities=49)

    result = inspect_path(source)

    assert result["is_r1_candidate"] is False
    assert "expected 50 commodity rows" in result["reason"]
