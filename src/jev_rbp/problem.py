"""Canonical, solver-independent RBP data model aligned with RAS v2.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CommodityType(StrEnum):
    MERCHANDISE = "Merchandise"
    INTERMODAL = "Intermodal"
    COAL = "Coal"
    GRAIN = "Grain"
    AUTOMOBILE = "Automobile"


class BlockType(StrEnum):
    MANIFEST = "Manifest"
    BULK = "Bulk"
    INTERMODAL = "Intermodal"
    MULTILEVEL = "Multilevel"


DIRECT_ONLY_COMMODITIES = frozenset({
    CommodityType.INTERMODAL,
    CommodityType.AUTOMOBILE,
})

CLASSIFICATION_BLOCK_TYPES = frozenset({
    BlockType.MANIFEST,
    BlockType.BULK,
    # RAS v2.0/v2.1 validator explicitly counts coal/grain classification
    # blocks. Those are demand-derived labels in the benchmark; keep the
    # explicit enum values available through BlockType for solution output.
})


def default_block_type(commodity_type: CommodityType) -> BlockType:
    if commodity_type is CommodityType.MERCHANDISE:
        return BlockType.MANIFEST
    if commodity_type in (CommodityType.COAL, CommodityType.GRAIN):
        return BlockType.BULK
    if commodity_type is CommodityType.INTERMODAL:
        return BlockType.INTERMODAL
    if commodity_type is CommodityType.AUTOMOBILE:
        return BlockType.MULTILEVEL
    raise ValueError(f"Unsupported commodity type: {commodity_type}")


@dataclass(frozen=True)
class Node:
    node_id: int
    node_type: str
    name: str = ""
    x_coord: float = 0.0
    y_coord: float = 0.0
    yard_type: str = ""
    yard_level: int = -1
    railroad_id: str = ""
    num_tracks: float = 0.0
    handling_capacity: float = 0.0
    handling_cost: float = 0.0
    is_interchange: bool = False
    allowed_commodities: str = ""
    allowed_traversal: str = ""
    datasource: str = ""


@dataclass(frozen=True)
class Link:
    link_id: int
    from_node_id: int
    to_node_id: int
    length: float
    capacity: float
    railroad_id: str = ""
    free_speed: float = 0.0
    tracks: float = 0.0
    geometry: str = ""


@dataclass(frozen=True)
class Demand:
    demand_id: int
    origin_yard_id: int
    dest_yard_id: int
    volume: int
    commodity_type: CommodityType

    def effective_volume(self, settings: "Settings") -> float:
        return float(self.volume) * settings.demand_multiplier


@dataclass(frozen=True)
class Settings:
    min_block_vol_short: float = 350.0
    min_block_vol_medium: float = 700.0
    min_block_vol_long: float = 1050.0
    max_circuitous_ratio: float = 1.3
    operating_cycle: int = 70
    block_fixed_cost: float = 2500.0
    transport_cost_coefficient: float = 1.0
    interchange_cost: float = 100.0
    stress_penalty_m: float = 5.0
    demand_multiplier: float = 1.0


@dataclass(frozen=True)
class Block:
    block_id: int
    from_yard_id: int
    to_yard_id: int
    block_type: BlockType
    volume: float = 0.0


@dataclass(frozen=True)
class BlockingSequence:
    demand_id: int
    block_ids: tuple[int, ...]
    volume: float


@dataclass(frozen=True)
class BlockRoute:
    block_id: int
    node_ids: tuple[int, ...] = ()
    link_ids: tuple[int, ...] = ()


@dataclass
class RBPInstance:
    nodes: dict[int, Node]
    links: dict[int, Link]
    demands: dict[int, Demand]
    settings: Settings = field(default_factory=Settings)


@dataclass
class Solution:
    blocks: dict[int, Block] = field(default_factory=dict)
    sequences: dict[int, BlockingSequence] = field(default_factory=dict)
    routes: dict[int, BlockRoute] = field(default_factory=dict)
