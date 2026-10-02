from jev_rbp.problem import (
    BlockType,
    CommodityType,
    Demand,
    Node,
    Settings,
    default_block_type,
)


def test_block_and_demand_types_are_distinct() -> None:
    assert default_block_type(CommodityType.MERCHANDISE) is BlockType.MANIFEST
    assert default_block_type(CommodityType.COAL) is BlockType.BULK
    assert default_block_type(CommodityType.GRAIN) is BlockType.BULK
    assert default_block_type(CommodityType.INTERMODAL) is BlockType.INTERMODAL
    assert default_block_type(CommodityType.AUTOMOBILE) is BlockType.MULTILEVEL


def test_demand_volume_stays_integer_and_scaling_is_explicit() -> None:
    demand = Demand(1, 10, 20, 101, CommodityType.MERCHANDISE)
    settings = Settings(demand_multiplier=0.5)
    assert demand.volume == 101
    assert demand.effective_volume(settings) == 50.5


def test_node_benchmark_metadata_is_supported() -> None:
    node = Node(
        1, "yard", "YARD", 10.0, 20.0, "hump", 1, "UP",
        20, 30000, 2.5, True, "merchandise,coal,grain", "all", "test"
    )
    assert node.x_coord == 10.0
    assert node.allowed_traversal == "all"
