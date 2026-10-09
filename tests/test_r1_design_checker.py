from __future__ import annotations

from pathlib import Path

from jev_rbp.r1_design_checker import check_instance


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    lines = [",".join(fields)]
    for row in rows:
        lines.append(",".join(str(row.get(field, "")) for field in fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_fixture(root: Path, *, connected: bool = True, bad_direct: bool = False) -> None:
    root.mkdir()
    yards = [
        {
            "node_id": i,
            "node_type": "yard",
            "yard_type": "hump" if i in (1, 2) else "flat",
            "num_tracks": 2 + (i % 3),
            "handling_capacity": 5000 + i * 1000,
            "handling_cost": 1 + (i % 3),
            "railroad_id": "BNSF" if i <= 4 else "CSX",
            "is_interchange": "TRUE" if i in (4, 5) else "FALSE",
        }
        for i in range(1, 9)
    ]
    _write_csv(
        root / "node.csv",
        yards,
        [
            "node_id",
            "node_type",
            "yard_type",
            "num_tracks",
            "handling_capacity",
            "handling_cost",
            "railroad_id",
            "is_interchange",
        ],
    )

    edges = []
    edge_id = 1
    chain = [(1, 2, 50), (2, 3, 150), (3, 4, 150), (4, 5, 150),
             (5, 6, 150), (6, 7, 150), (7, 8, 150), (8, 1, 220)]
    chords = [(2, 7, 260), (3, 6, 260), (4, 8, 250)]
    for u, v, length in chain + chords:
        if not connected and (u == 8 or v == 8):
            continue
        edges.append(
            {
                "link_id": edge_id,
                "from_node_id": u,
                "to_node_id": v,
                "length": length,
                "capacity": 4000 if edge_id % 4 else 2500,
            }
        )
        edge_id += 1
    _write_csv(
        root / "link.csv",
        edges,
        ["link_id", "from_node_id", "to_node_id", "length", "capacity"],
    )

    types = (
        ["Merchandise"] * 20
        + ["Coal"] * 10
        + ["Grain"] * 10
        + ["Intermodal"] * 5
        + ["Automobile"] * 5
    )
    demands = []
    pairs = [(1, 5), (2, 6), (3, 7), (4, 8), (1, 6), (2, 7), (3, 8), (4, 1)]
    for i, dtype in enumerate(types, start=1):
        origin, dest = pairs[(i - 1) % len(pairs)]
        volume = 1400 if dtype in {"Intermodal", "Automobile"} else 900 + (i % 5) * 100
        if bad_direct and dtype in {"Intermodal", "Automobile"}:
            volume = 100
        demands.append(
            {
                "demand_id": i,
                "origin_yard_id": origin,
                "dest_yard_id": dest,
                "volume": volume,
                "block_type": dtype,
            }
        )
    _write_csv(
        root / "demand.csv",
        demands,
        ["demand_id", "origin_yard_id", "dest_yard_id", "volume", "block_type"],
    )

    settings = [
        ("min_block_vol_short(<100mi)", 350),
        ("min_block_vol_med(100-500mi)", 700),
        ("min_block_vol_long(>500mi)", 1050),
        ("max_circuitous_ratio", 1.3),
    ]
    _write_csv(
        root / "setting.csv",
        [{"parameter": k, "value": v} for k, v in settings],
        ["parameter", "value"],
    )


def test_shape_and_type_checks(tmp_path: Path) -> None:
    root = tmp_path / "instance"
    _make_fixture(root)
    report = check_instance(root)
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["input_files"] == "PASS"
    assert statuses["yard_count"] == "PASS"
    assert statuses["demand_count"] == "PASS"
    assert statuses["demand_type_distribution"] == "PASS"


def test_disconnected_network_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "instance"
    _make_fixture(root, connected=False)
    report = check_instance(root)
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["physical_connectivity"] == "FAIL"
    assert report.status == "FAIL"


def test_direct_only_volume_is_checked(tmp_path: Path) -> None:
    root = tmp_path / "instance"
    _make_fixture(root, bad_direct=True)
    report = check_instance(root)
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["direct_only_demands"] == "FAIL"


def test_dynamic_phenomena_require_search_evidence(tmp_path: Path) -> None:
    root = tmp_path / "instance"
    _make_fixture(root)
    report = check_instance(root)
    statuses = {check.name: check.status for check in report.checks}
    assert all(statuses[f"P{i}"] == "NOT_EVALUATED" for i in range(1, 8))

    evidence = {
        "phenomena": {
            f"P{i}": {"observed": True, "summary": f"observed P{i}"}
            for i in range(1, 8)
        }
    }
    report = check_instance(root, evidence=evidence)
    statuses = {check.name: check.status for check in report.checks}
    assert all(statuses[f"P{i}"] == "PASS" for i in range(1, 8))


def test_legacy_plural_filenames_are_accepted(tmp_path: Path) -> None:
    root = tmp_path / "instance"
    _make_fixture(root)
    for singular, plural in (
        ("node.csv", "nodes.csv"),
        ("link.csv", "links.csv"),
        ("demand.csv", "demands.csv"),
        ("setting.csv", "settings.csv"),
    ):
        (root / singular).rename(root / plural)

    report = check_instance(root)
    assert next(c for c in report.checks if c.name == "input_files").status == "PASS"
