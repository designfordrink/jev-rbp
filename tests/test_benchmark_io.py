from jev_rbp.benchmark_io import solution_from_json, solution_to_json
from jev_rbp.problem import (
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


def _instance_and_solution():
    instance = RBPInstance(
        nodes={
            1: Node(1, "yard", num_tracks=2, handling_capacity=100, handling_cost=4.0),
            2: Node(2, "yard", num_tracks=2, handling_capacity=100, handling_cost=6.0),
        },
        links={10: Link(10, 1, 2, 12.0, 100.0)},
        demands={1: Demand(1, 1, 2, 20, CommodityType.MERCHANDISE)},
        settings=Settings(
            min_block_vol_short=5.0,
            min_block_vol_medium=10.0,
            min_block_vol_long=15.0,
            block_fixed_cost=100.0,
        ),
    )
    solution = Solution(
        blocks={7: Block(7, 1, 2, BlockType.MANIFEST, 20.0)},
        sequences={1: BlockingSequence(1, (7,), 20.0)},
        routes={7: BlockRoute(7, (1, 2), (10,))},
    )
    return instance, solution


def test_public_json_round_trip_preserves_canonical_model():
    instance, solution = _instance_and_solution()

    payload = solution_to_json(instance, solution)
    restored_instance, restored_solution = solution_from_json(payload)

    assert restored_instance == instance
    assert restored_solution == solution


def test_public_json_uses_benchmark_field_names():
    instance, solution = _instance_and_solution()

    payload = solution_to_json(instance, solution)

    assert payload["outputs"]["1 Block Design"][0]["block_type"] == "Manifest"
    assert payload["outputs"]["2 Blocking Sequence"][0]["blocking_sequence"] == "7"
    assert payload["outputs"]["3 Block Route"][0]["physical_path_links"] == "10"
    assert payload["inputs"]["demands"][0]["commodity_id"] == 1


def test_public_json_accepts_legacy_block_commodity_type_alias():
    payload = {
        "inputs": {
            "settings": {},
            "nodes": [
                {"node_id": 1, "node_type": "yard"},
                {"node_id": 2, "node_type": "yard"},
            ],
            "links": [
                {"link_id": 10, "from_node_id": 1, "to_node_id": 2, "length": 12, "capacity": 100}
            ],
            "demands": [
                {
                    "commodity_id": 1,
                    "commodity_type": "Merchandise",
                    "origin_yard_id": 1,
                    "dest_yard_id": 2,
                    "volume": 20,
                }
            ],
        },
        "outputs": {
            "1 Block Design": [
                {
                    "block_id": 7,
                    "from_yard_id": 1,
                    "to_yard_id": 2,
                    "commodity_type": "Manifest",
                    "block_volume": 20,
                }
            ],
            "2 Blocking Sequence": [
                {
                    "commodity_id": 1,
                    "commodity_type": "Merchandise",
                    "origin_yard_id": 1,
                    "dest_yard_id": 2,
                    "volume": 20,
                    "blocking_sequence": "7",
                }
            ],
            "3 Block Route": [
                {
                    "block_id": 7,
                    "from_yard_id": 1,
                    "to_yard_id": 2,
                    "physical_path_nodes": "1 -> 2",
                    "physical_path_links": "10",
                }
            ],
        },
    }

    _, solution = solution_from_json(payload)

    assert solution.blocks[7].block_type is BlockType.MANIFEST
    assert solution.sequences[1].block_ids == (7,)
