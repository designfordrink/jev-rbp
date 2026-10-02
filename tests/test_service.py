from jev_rbp.problem import (
    Block,
    BlockType,
    CommodityType,
    Demand,
    Link,
    Node,
    RBPInstance,
)
from jev_rbp.routing import DijkstraRouter
from jev_rbp.service import BlockServiceRouter


def instance():
    return RBPInstance(
        nodes={
            1: Node(1, "yard", handling_cost=2.0),
            2: Node(2, "yard", handling_cost=3.0),
            3: Node(3, "yard", handling_cost=5.0),
        },
        links={
            1: Link(1, 1, 2, 10.0, 1000.0),
            2: Link(2, 2, 3, 15.0, 1000.0),
            3: Link(3, 1, 3, 40.0, 1000.0),
        },
        demands={},
    )


def test_service_graph_routes_through_blocks():
    inst = instance()
    blocks = [
        Block(10, 1, 2, BlockType.MANIFEST),
        Block(11, 2, 3, BlockType.MANIFEST),
        Block(12, 1, 3, BlockType.MANIFEST),
    ]

    route = BlockServiceRouter(inst, DijkstraRouter(inst)).route(
        1, 3, CommodityType.MERCHANDISE, blocks
    )

    assert route is not None
    assert route.block_ids == (10, 11)
    assert route.cost_per_car == 28.0


def test_service_graph_rejects_wrong_commodity_block_type():
    inst = instance()
    blocks = [Block(10, 1, 3, BlockType.BULK)]

    route = BlockServiceRouter(inst, DijkstraRouter(inst)).route(
        1, 3, CommodityType.MERCHANDISE, blocks
    )

    assert route is None
