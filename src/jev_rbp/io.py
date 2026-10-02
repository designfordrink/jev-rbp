"""GMNS/RAS v2.1 CSV loader."""

from __future__ import annotations

import csv
from pathlib import Path

from .problem import CommodityType, Demand, Link, Node, RBPInstance, Settings


def _bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _float(value: str | None, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def load_instance(directory: str | Path) -> RBPInstance:
    root = Path(directory)

    nodes = {}
    with (root / "node.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            node_id = int(row["node_id"])
            nodes[node_id] = Node(
                node_id=node_id,
                node_type=row.get("node_type", ""),
                name=row.get("name", ""),
                x_coord=_float(row.get("x_coord")),
                y_coord=_float(row.get("y_coord")),
                yard_type=row.get("yard_type", ""),
                yard_level=int(float(row.get("yard_level", -1) or -1)),
                railroad_id=row.get("railroad_id", ""),
                num_tracks=_float(row.get("num_tracks")),
                handling_capacity=_float(row.get("handling_capacity")),
                handling_cost=_float(row.get("handling_cost")),
                is_interchange=_bool(row.get("is_interchange")),
                allowed_commodities=row.get("allowed_commodities", ""),
                allowed_traversal=row.get("allowed_traversal", ""),
                datasource=row.get("datasource", ""),
            )

    links = {}
    with (root / "link.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            link_id = int(row["link_id"])
            links[link_id] = Link(
                link_id=link_id,
                from_node_id=int(row["from_node_id"]),
                to_node_id=int(row["to_node_id"]),
                length=_float(row.get("length")),
                capacity=_float(row.get("capacity")),
                railroad_id=row.get("railroad_id", ""),
                free_speed=_float(row.get("free_speed")),
                tracks=_float(row.get("tracks")),
                geometry=row.get("geometry", ""),
            )

    demands = {}
    with (root / "demand.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            demand_id = int(row["demand_id"])
            demands[demand_id] = Demand(
                demand_id=demand_id,
                origin_yard_id=int(row["origin_yard_id"]),
                dest_yard_id=int(row["dest_yard_id"]),
                volume=int(row["volume"]),
                commodity_type=CommodityType(row["block_type"]),
            )

    values: dict[str, str] = {}
    setting_path = root / "setting.csv"
    if setting_path.exists():
        with setting_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = row.get("parameter")
                value = row.get("value")
                if key and value is not None:
                    values[key] = value

    settings = Settings(
        min_block_vol_short=_float(values.get("min_block_vol_short(<100mi)"), 350.0),
        min_block_vol_medium=_float(values.get("min_block_vol_med(100-500mi)"), 700.0),
        min_block_vol_long=_float(values.get("min_block_vol_long(>500mi)"), 1050.0),
        max_circuitous_ratio=_float(values.get("max_circuitous_ratio"), 1.3),
        operating_cycle=int(float(values.get("operating_cycle", 70))),
        block_fixed_cost=_float(values.get("block_fixed_cost"), 2500.0),
        transport_cost_coefficient=_float(values.get("transport_cost_coefficient"), 1.0),
        interchange_cost=_float(values.get("interchange_cost"), 100.0),
        stress_penalty_m=_float(values.get("stress_penalty_M"), 5.0),
        demand_multiplier=_float(values.get("demand_multiplier"), 1.0),
    )
    return RBPInstance(nodes=nodes, links=links, demands=demands, settings=settings)
