from jev_rbp.actions import DropAction
from jev_rbp.dataset import make_rbp_feature_extractor
from jev_rbp.moves import ExactRBPMoveEvaluator, MoveContext
from jev_rbp.problem import (
    Block,
    BlockRoute,
    BlockingSequence,
    BlockType,
    CommodityType,
    Demand,
    Link,
    Node,
    RBPInstance,
    Settings,
    Solution,
)
from jev_rbp.routing import DijkstraRouter


def _duplicate_instance():
    return RBPInstance(
        nodes={
            1: Node(1, "yard", num_tracks=2),
            2: Node(2, "yard", num_tracks=2),
            3: Node(3, "yard", num_tracks=2),
        },
        links={
            1: Link(1, 1, 2, 10.0, 1000.0),
            2: Link(2, 2, 3, 15.0, 1000.0),
        },
        demands={
            1: Demand(1, 1, 3, 20, CommodityType.MERCHANDISE),
        },
        settings=Settings(
            min_block_vol_short=5.0,
            min_block_vol_medium=10.0,
            min_block_vol_long=15.0,
            block_fixed_cost=100.0,
            transport_cost_coefficient=1.0,
        ),
    )


def _duplicate_state():
    route = BlockRoute(10, (1, 2, 3), (1, 2))
    return Solution(
        blocks={
            10: Block(10, 1, 3, BlockType.MANIFEST, 20.0),
            11: Block(11, 1, 3, BlockType.MANIFEST, 20.0),
        },
        sequences={
            1: BlockingSequence(1, (10,), 20.0),
        },
        routes={
            10: route,
            11: BlockRoute(11, (1, 2, 3), (1, 2)),
        },
    )


def test_exact_drop_of_unused_duplicate_is_improving():
    instance = _duplicate_instance()
    router = DijkstraRouter(instance)
    evaluator = ExactRBPMoveEvaluator(MoveContext(instance, router))

    evaluation = evaluator.evaluate(_duplicate_state(), DropAction(11))

    assert evaluation.feasible
    assert evaluation.delta == -100.0


def test_jev_context_exposes_whether_drop_block_is_used():
    instance = _duplicate_instance()
    router = DijkstraRouter(instance)
    extractor = make_rbp_feature_extractor(instance, router)
    state = _duplicate_state()

    used = extractor(state, DropAction(10), "drop", 0)
    unused = extractor(state, DropAction(11), "drop", 1)

    assert used["drop_used_by_demand_count"] == 1.0
    assert used["drop_unused"] == 0.0
    assert unused["drop_used_by_demand_count"] == 0.0
    assert unused["drop_unused"] == 1.0
