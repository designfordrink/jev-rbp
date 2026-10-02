from jev_rbp.problem import (
    Block,
    BlockType,
    CommodityType,
    Demand,
    Link,
    Node,
    RBPInstance,
)
from jev_rbp.rerouting import reroute
from jev_rbp.routing import DijkstraRouter


def test_reroute_aggregates_block_volume_and_drops_unused_blocks():
    inst = RBPInstance(
        nodes={
            1: Node(1, "yard"),
            2: Node(2, "yard"),
            3: Node(3, "yard"),
        },
        links={
            1: Link(1, 1, 2, 10.0, 1000.0),
            2: Link(2, 2, 3, 10.0, 1000.0),
        },
        demands={
            1: Demand(1, 1, 3, 100, CommodityType.MERCHANDISE),
        },
    )
    open_blocks = {
        10: Block(10, 1, 2, BlockType.MANIFEST),
        11: Block(11, 2, 3, BlockType.MANIFEST),
        12: Block(12, 3, 1, BlockType.MANIFEST),
    }

    result = reroute(inst, open_blocks, DijkstraRouter(inst))

    assert result.solution is not None
    assert set(result.solution.blocks) == {10, 11}
    assert result.solution.blocks[10].volume == 100.0
    assert result.solution.blocks[11].volume == 100.0
    assert result.solution.sequences[1].block_ids == (10, 11)
