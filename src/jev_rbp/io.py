"""GMNS/RAS CSV loader for the canonical RBP model."""

from __future__ import annotations

import csv
from pathlib import Path

from .problem import CommodityType, Demand, Link, Node, RBPInstance, Settings


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def load_instance(directory: str | Path) -> RBPInstance:
    root = Path(directory)

    nodes: dict[int, Node] = {}
    with (root / "node.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            node_id = int(row["node_id"])
            nodes[node_id] = Node(
                node_id=node_id,
                node_type=row.get("node_type", ""),
                name=row.get("name", ""),
                yard_type=row.get("yard_type", ""),
                yard_level=int(float(row.get("yard_level", -1) or -1)),
                railroad_id=row.get("railroad_id", ""),
                num_tracks=float(row.get("num_tracks", 0) or 0),
                handling_capacity=float(row.get("handling_capacity", 0) or 0),
                handling_cost=float(row.get("handling_cost", 0) or 0),
                is_interchange=_bool(row.get("is_interchange", "False")),
            )

    links: dict[int, Link] = {}
    with (root / "link.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            link_id = int(row["link_id"])
            links[link_id] = Link(
                link_id=link_id,
                from_node_id=int(row["from_node_id"]),
                to_node_id=int(row["to_node_id"]),
                length=float(row["length"]),
                capacity=float(row["capacity"]),
                railroad_id=row.get("railroad_id", ""),
            )

    demands: dict[int, Demand] = {}
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

    settings = Settings()
    setting_path = root / "setting.csv"
    if setting_path.exists():
        values: dict[str, str] = {}
        with setting_path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = row.get("parameter") or row.get("name") or row.get("setting")
                value = row.get("value")
                if key and value is not None:
                    values[key] = value
        settings = Settings(
            demand_multiplier=float(values.get("demand_multiplier", 1.0)),
            block_fixed_cost=float(values.get("block_fixed_cost", 2500.0)),
            transport_cost_coefficient=float(
                values.get("transport_cost_coefficient", 1.0)
            ),
            interchange_cost=float(values.get("interchange_cost", 100.0)),
            max_circuitous_ratio=float(values.get("max_circuitous_ratio", 1.3)),
        )

    return RBPInstance(nodes=nodes, links=links, demands=demands, settings=settings)
