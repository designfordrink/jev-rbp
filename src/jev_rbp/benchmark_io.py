"""Adapter for the public RAS solution_result.json contract.

The adapter is intentionally thin: it converts the external JSON representation
into the clean-room RBP model and back without embedding solver logic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .problem import (
    Block,
    BlockRoute,
    BlockType,
    BlockingSequence,
    CommodityType,
    Demand,
    Link,
    Node,
    RBPInstance,
    Settings,
    Solution,
)

_BLOCK_TYPES = {member.value: member for member in BlockType}
_COMMODITY_TYPES = {member.value: member for member in CommodityType}


def _parse_ids(value: str | None) -> tuple[int, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(int(part.strip()) for part in text.split("->"))


def _arrow_ids(values: tuple[int, ...]) -> str:
    return " -> ".join(str(value) for value in values)


def _integer(value: float, field_name: str) -> int:
    if not float(value).is_integer():
        raise ValueError(f"{field_name}={value!r} is not representable by the benchmark integer schema")
    return int(value)


def solution_from_json(payload: dict[str, Any]) -> tuple[RBPInstance, Solution]:
    """Parse a public RAS solution_result-style payload."""
    inputs = payload["inputs"]
    outputs = payload["outputs"]

    settings_data = inputs.get("settings", {})
    settings = Settings(
        min_block_vol_short=float(settings_data.get("min_block_vol_short(<100mi)", 350.0)),
        min_block_vol_medium=float(settings_data.get("min_block_vol_med(100-500mi)", 700.0)),
        min_block_vol_long=float(settings_data.get("min_block_vol_long(>500mi)", 1050.0)),
        max_circuitous_ratio=float(settings_data.get("max_circuitous_ratio", 1.3)),
        operating_cycle=int(settings_data.get("operating_cycle", 70)),
        block_fixed_cost=float(settings_data.get("block_fixed_cost", 2500.0)),
        transport_cost_coefficient=float(settings_data.get("transport_cost_coefficient", 1.0)),
        interchange_cost=float(settings_data.get("interchange_cost", 100.0)),
        stress_penalty_m=float(settings_data.get("stress_penalty_M", 5.0)),
        demand_multiplier=float(settings_data.get("demand_multiplier", 1.0)),
    )

    nodes: dict[int, Node] = {}
    for row in inputs.get("nodes", []):
        node_id = int(row["node_id"])
        nodes[node_id] = Node(
            node_id=node_id,
            node_type=str(row.get("node_type", "")),
            name=str(row.get("name", "")),
            x_coord=float(row.get("x_coord", 0.0)),
            y_coord=float(row.get("y_coord", 0.0)),
            yard_type=str(row.get("yard_type", "")),
            yard_level=int(row.get("yard_level", -1)),
            railroad_id=str(row.get("railroad_id", "")),
            num_tracks=float(row.get("num_tracks", 0.0)),
            handling_capacity=float(row.get("handling_capacity", 0.0)),
            handling_cost=float(row.get("handling_cost", 0.0)),
            is_interchange=bool(row.get("is_interchange", False)),
            allowed_commodities=str(row.get("allowed_commodities", "")),
            allowed_traversal=str(row.get("allowed_traversal", "")),
            datasource=str(row.get("datasource", "")),
        )

    links: dict[int, Link] = {}
    for row in inputs.get("links", []):
        link_id = int(row["link_id"])
        links[link_id] = Link(
            link_id=link_id,
            from_node_id=int(row["from_node_id"]),
            to_node_id=int(row["to_node_id"]),
            length=float(row.get("length", 0.0)),
            capacity=float(row.get("capacity", 0.0)),
            railroad_id=str(row.get("railroad_id", "")),
            free_speed=float(row.get("free_speed", 0.0)),
            tracks=float(row.get("tracks", 0.0)),
            geometry=str(row.get("geometry", "")),
        )

    demands: dict[int, Demand] = {}
    for row in inputs.get("demands", []):
        demand_id = int(row["commodity_id"])
        demands[demand_id] = Demand(
            demand_id=demand_id,
            origin_yard_id=int(row["origin_yard_id"]),
            dest_yard_id=int(row["dest_yard_id"]),
            volume=int(row["volume"]),
            commodity_type=_COMMODITY_TYPES[str(row["commodity_type"])],
        )

    blocks: dict[int, Block] = {}
    for row in outputs.get("1 Block Design", []):
        block_id = int(row["block_id"])
        raw_type = row.get("block_type", row.get("commodity_type"))
        blocks[block_id] = Block(
            block_id=block_id,
            from_yard_id=int(row["from_yard_id"]),
            to_yard_id=int(row["to_yard_id"]),
            block_type=_BLOCK_TYPES[str(raw_type)],
            volume=float(row.get("block_volume", 0)),
        )

    sequences: dict[int, BlockingSequence] = {}
    for row in outputs.get("2 Blocking Sequence", []):
        demand_id = int(row["commodity_id"])
        sequences[demand_id] = BlockingSequence(
            demand_id=demand_id,
            block_ids=_parse_ids(row["blocking_sequence"]),
            volume=float(row["volume"]),
        )

    routes: dict[int, BlockRoute] = {}
    for row in outputs.get("3 Block Route", []):
        block_id = int(row["block_id"])
        routes[block_id] = BlockRoute(
            block_id=block_id,
            node_ids=_parse_ids(row.get("physical_path_nodes")),
            link_ids=_parse_ids(row.get("physical_path_links")),
        )

    instance = RBPInstance(nodes=nodes, links=links, demands=demands, settings=settings)
    return instance, Solution(blocks=blocks, sequences=sequences, routes=routes)


def solution_to_json(instance: RBPInstance, solution: Solution) -> dict[str, Any]:
    """Serialize the clean-room model to a public RAS solution_result payload."""
    inputs = {
        "settings": {
            "min_block_vol_short(<100mi)": instance.settings.min_block_vol_short,
            "min_block_vol_med(100-500mi)": instance.settings.min_block_vol_medium,
            "min_block_vol_long(>500mi)": instance.settings.min_block_vol_long,
            "max_circuitous_ratio": instance.settings.max_circuitous_ratio,
            "operating_cycle": instance.settings.operating_cycle,
            "block_fixed_cost": instance.settings.block_fixed_cost,
            "transport_cost_coefficient": instance.settings.transport_cost_coefficient,
            "interchange_cost": instance.settings.interchange_cost,
            "stress_penalty_M": instance.settings.stress_penalty_m,
            "demand_multiplier": instance.settings.demand_multiplier,
        },
        "nodes": [
            {
                "node_id": node.node_id,
                "node_type": node.node_type,
                "name": node.name,
                "x_coord": node.x_coord,
                "y_coord": node.y_coord,
                "yard_type": node.yard_type,
                "yard_level": node.yard_level,
                "railroad_id": node.railroad_id,
                "num_tracks": node.num_tracks,
                "handling_capacity": node.handling_capacity,
                "handling_cost": node.handling_cost,
                "is_interchange": node.is_interchange,
                "allowed_commodities": node.allowed_commodities,
                "allowed_traversal": node.allowed_traversal,
                "datasource": node.datasource,
            }
            for node in instance.nodes.values()
        ],
        "links": [
            {
                "link_id": link.link_id,
                "from_node_id": link.from_node_id,
                "to_node_id": link.to_node_id,
                "length": link.length,
                "capacity": link.capacity,
                "railroad_id": link.railroad_id,
                "free_speed": link.free_speed,
                "tracks": link.tracks,
                "geometry": link.geometry,
            }
            for link in instance.links.values()
        ],
        "demands": [
            {
                "commodity_id": demand.demand_id,
                "commodity_type": demand.commodity_type.value,
                "origin_yard_id": demand.origin_yard_id,
                "dest_yard_id": demand.dest_yard_id,
                "volume": demand.volume,
            }
            for demand in instance.demands.values()
        ],
    }

    block_design = []
    for block in solution.blocks.values():
        volume = _integer(block.volume, f"block {block.block_id} block_volume")
        block_design.append(
            {
                "block_id": block.block_id,
                "from_yard_id": block.from_yard_id,
                "to_yard_id": block.to_yard_id,
                "block_type": block.block_type.value,
                "block_volume": volume,
            }
        )

    sequences = []
    for demand_id, sequence in solution.sequences.items():
        demand = instance.demands[demand_id]
        volume = _integer(sequence.volume, f"demand {demand_id} sequence volume")
        sequences.append(
            {
                "commodity_id": demand_id,
                "commodity_type": demand.commodity_type.value,
                "origin_yard_id": demand.origin_yard_id,
                "dest_yard_id": demand.dest_yard_id,
                "volume": volume,
                "blocking_sequence": _arrow_ids(sequence.block_ids),
            }
        )

    routes = []
    for block_id, route in solution.routes.items():
        block = solution.blocks[block_id]
        routes.append(
            {
                "block_id": block_id,
                "from_yard_id": block.from_yard_id,
                "to_yard_id": block.to_yard_id,
                "physical_path_nodes": _arrow_ids(route.node_ids),
                "physical_path_links": _arrow_ids(route.link_ids),
            }
        )

    return {
        "inputs": inputs,
        "outputs": {
            "1 Block Design": block_design,
            "2 Blocking Sequence": sequences,
            "3 Block Route": routes,
        },
    }


def load_solution_json(path: str | Path) -> tuple[RBPInstance, Solution]:
    """Load a solution_result JSON file."""
    with Path(path).open(encoding="utf-8") as handle:
        return solution_from_json(json.load(handle))


def save_solution_json(
    path: str | Path,
    instance: RBPInstance,
    solution: Solution,
) -> None:
    """Write a clean-room solution in public RAS JSON format."""
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(solution_to_json(instance, solution), handle, indent=2)
        handle.write("\n")
