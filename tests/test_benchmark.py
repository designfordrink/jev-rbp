from jev_rbp.benchmark import BenchmarkAuthority
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


def _instance(capacity=1000.0, handling_capacity=1000.0):
    return RBPInstance(
        nodes={
            1: Node(
                1, "yard", num_tracks=2, handling_capacity=handling_capacity,
                handling_cost=4.0, railroad_id="BNSF",
            ),
            2: Node(
                2, "yard", num_tracks=2, handling_capacity=handling_capacity,
                handling_cost=6.0, railroad_id="BNSF",
            ),
            3: Node(
                3, "yard", num_tracks=2, handling_capacity=handling_capacity,
                handling_cost=8.0, railroad_id="BNSF",
            ),
        },
        links={
            1: Link(1, 1, 2, 10.0, capacity),
            2: Link(2, 2, 3, 15.0, capacity),
            3: Link(3, 1, 3, 40.0, capacity),
        },
        demands={
            1: Demand(1, 1, 3, 20, CommodityType.MERCHANDISE),
            2: Demand(2, 1, 3, 10, CommodityType.INTERMODAL),
        },
        settings=Settings(
            min_block_vol_short=5.0,
            min_block_vol_medium=10.0,
            min_block_vol_long=15.0,
            max_circuitous_ratio=1.3,
            block_fixed_cost=100.0,
            transport_cost_coefficient=1.0,
            interchange_cost=100.0,
            stress_penalty_m=5.0,
        ),
    )


def _valid_solution():
    return Solution(
        blocks={
            10: Block(10, 1, 3, BlockType.MANIFEST, 999.0),
            11: Block(11, 1, 3, BlockType.INTERMODAL, 999.0),
        },
        sequences={
            1: BlockingSequence(1, (10,), 20.0),
            2: BlockingSequence(2, (11,), 10.0),
        },
        routes={
            10: BlockRoute(10, (1, 3), (3,)),
            11: BlockRoute(11, (1, 3), (3,)),
        },
    )


def test_valid_solution_passes_all_benchmark_checks():
    report = BenchmarkAuthority(_instance()).validate(_valid_solution())

    assert report.feasible
    assert report.violations == []
    assert report.cost is not None
    assert report.cost.fixed == 200.0
    assert report.cost.transport == 1200.0
    assert report.cost.handling == 0.0
    assert report.cost.total == 1400.0
    assert report.stress is not None
    assert report.stress.unserved_demand_cars == 0.0
    assert report.stress.stress_score == 1400.0


def test_benchmark_uses_sequence_volume_not_block_design_volume():
    solution = _valid_solution()
    solution.blocks[10] = Block(10, 1, 3, BlockType.MANIFEST, 1.0)

    report = BenchmarkAuthority(_instance()).validate(solution)

    assert report.feasible
    assert report.cost.transport == 1200.0


def test_link_capacity_is_independent_benchmark_constraint():
    report = BenchmarkAuthority(_instance(capacity=25.0)).validate(_valid_solution())

    assert not report.feasible
    assert any(v.startswith("C5:") for v in report.violations)


def test_handling_capacity_is_checked_at_intermediate_yard():
    instance = _instance(handling_capacity=10.0)
    solution = Solution(
        blocks={
            10: Block(10, 1, 2, BlockType.MANIFEST, 20.0),
            11: Block(11, 2, 3, BlockType.MANIFEST, 20.0),
        },
        sequences={1: BlockingSequence(1, (10, 11), 20.0)},
        routes={
            10: BlockRoute(10, (1, 2), (1,)),
            11: BlockRoute(11, (2, 3), (2,)),
        },
    )

    report = BenchmarkAuthority(instance).validate(solution)

    assert not report.feasible
    assert any(v.startswith("C3:") for v in report.violations)


def test_direct_only_commodity_must_use_its_direct_od_block():
    instance = _instance()
    solution = _valid_solution()
    solution.blocks[11] = Block(11, 1, 2, BlockType.INTERMODAL, 10.0)
    solution.blocks[12] = Block(12, 2, 3, BlockType.INTERMODAL, 10.0)
    solution.sequences[2] = BlockingSequence(2, (11, 12), 10.0)
    solution.routes[11] = BlockRoute(11, (1, 2), (1,))
    solution.routes[12] = BlockRoute(12, (2, 3), (2,))

    report = BenchmarkAuthority(instance).validate(solution)

    assert not report.feasible
    assert any(v.startswith("C9:") for v in report.violations)


def test_subtour_is_rejected_even_when_endpoints_match():
    instance = _instance()
    solution = Solution(
        blocks={
            10: Block(10, 1, 2, BlockType.MANIFEST, 20.0),
            11: Block(11, 2, 1, BlockType.MANIFEST, 20.0),
            12: Block(12, 1, 3, BlockType.MANIFEST, 20.0),
        },
        sequences={1: BlockingSequence(1, (10, 11, 12), 20.0)},
        routes={
            10: BlockRoute(10, (1, 2), (1,)),
            11: BlockRoute(11, (2, 1), (1,)),
            12: BlockRoute(12, (1, 3), (3,)),
        },
    )

    report = BenchmarkAuthority(instance).validate(solution)

    assert not report.feasible
    assert any(v.startswith("C1b:") for v in report.violations)


def test_underserved_demand_is_feasible_but_penalized_by_stress():
    instance = _instance()
    solution = _valid_solution()
    solution.sequences[1] = BlockingSequence(1, (10,), 10.0)

    report = BenchmarkAuthority(instance).validate(solution)

    assert report.feasible
    assert report.stress is not None
    assert report.stress.unserved_demand_cars == 10.0
    assert report.stress.unserved_car_miles == 400.0
    assert report.stress.stress_score == 3400.0
