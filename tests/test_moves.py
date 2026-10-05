from jev_rbp.actions import AddAction, DropAction
from jev_rbp.moves import (
    ExactRBPMoveEvaluator,
    MoveContext,
    RBPMoveGenerator,
    RBPMoveApplier,
)
from jev_rbp.problem import (
    Block,
    BlockType,
    BlockingSequence,
    BlockRoute,
    CommodityType,
    Demand,
    Link,
    Node,
    RBPInstance,
    Settings,
    Solution,
)
from jev_rbp.routing import DijkstraRouter
from jev_rbp.objective import evaluate_solution


def _instance():
    return RBPInstance(
        nodes={
            1: Node(1, "yard", num_tracks=3, handling_cost=4.0),
            2: Node(2, "yard", num_tracks=3, handling_cost=6.0),
            3: Node(3, "yard", num_tracks=3, handling_cost=8.0),
        },
        links={
            1: Link(1, 1, 2, 10.0, 1000.0),
            2: Link(2, 2, 3, 15.0, 1000.0),
            3: Link(3, 1, 3, 40.0, 1000.0),
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


def _via_state():
    return Solution(
        blocks={
            10: Block(10, 1, 2, BlockType.MANIFEST, 20.0),
            11: Block(11, 2, 3, BlockType.MANIFEST, 20.0),
        },
        sequences={
            1: BlockingSequence(1, (10, 11), 20.0),
        },
        routes={
            10: BlockRoute(10, (1, 2), (1,)),
            11: BlockRoute(11, (2, 3), (2,)),
        },
    )


def test_exact_add_evaluation_includes_handling_and_rerouting():
    instance = _instance()
    router = DijkstraRouter(instance)
    evaluator = ExactRBPMoveEvaluator(MoveContext(instance, router))

    evaluation = evaluator.evaluate(
        _via_state(),
        AddAction(1, 3, CommodityType.MERCHANDISE),
    )

    assert evaluation.feasible
    assert evaluation.objective_before == 820.0
    assert evaluation.objective_after == 600.0
    assert evaluation.delta == -220.0


def test_exact_drop_rejects_unroutable_move():
    instance = _instance()
    router = DijkstraRouter(instance)
    evaluator = ExactRBPMoveEvaluator(MoveContext(instance, router))

    evaluation = evaluator.evaluate(_via_state(), DropAction(10))

    assert not evaluation.feasible
    assert evaluation.objective_before == 820.0


def test_candidate_generator_is_deterministic_and_phase_specific():
    instance = _instance()
    context = MoveContext(instance, DijkstraRouter(instance))
    generator = RBPMoveGenerator(context)

    drop = generator.generate_phase(_via_state(), "drop")
    add = generator.generate_phase(_via_state(), "add")
    swap = generator.generate_phase(_via_state(), "swap")

    assert [action.block_id for action in drop] == [10, 11]
    assert len(add) == 4
    assert len(swap) == 8



def test_candidate_yard_filter_is_optional():
    nodes = {
        1: Node(1, "yard"),
        2: Node(2, "yard"),
        3: Node(3, "yard"),
    }
    instance = RBPInstance(nodes=nodes, links={}, demands={}, settings=Settings())
    generator = RBPMoveGenerator(
        MoveContext(instance, DijkstraRouter(instance)),
        candidate_yards={1, 2},
    )

    assert generator._build_candidates() == ()


def test_move_objective_matches_benchmark_and_includes_interchange():
    instance = _instance()
    instance.nodes[1] = Node(
        1, "yard", num_tracks=3, handling_cost=4.0, railroad_id="BNSF"
    )
    instance.nodes[3] = Node(
        3, "yard", num_tracks=3, handling_cost=8.0, railroad_id="CSXT"
    )
    router = DijkstraRouter(instance)
    evaluator = ExactRBPMoveEvaluator(MoveContext(instance, router))

    evaluation = evaluator.evaluate(
        _via_state(),
        AddAction(1, 3, CommodityType.MERCHANDISE),
    )

    assert evaluation.feasible
    from jev_rbp.benchmark import BenchmarkAuthority

    candidate = RBPMoveApplier(MoveContext(instance, router)).apply(
        _via_state(),
        AddAction(1, 3, CommodityType.MERCHANDISE),
    )
    objective = evaluate_solution(instance, candidate, router)
    benchmark = BenchmarkAuthority(instance).validate(candidate)

    assert benchmark.feasible
    assert benchmark.cost is not None
    assert objective.total == benchmark.cost.total
    assert objective.interchange > 0.0
    assert evaluation.objective_after == benchmark.cost.total
