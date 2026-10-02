from jev_rbp.greedy import build_greedy_solution
from jev_rbp.objective import evaluate_direct_solution
from jev_rbp.problem import CommodityType, Demand, Link, Node, RBPInstance
from jev_rbp.routing import DijkstraRouter
from jev_rbp.validator import RBPValidator


def instance():
    return RBPInstance(
        nodes={1: Node(1, "yard"), 2: Node(2, "yard"), 3: Node(3, "yard")},
        links={
            1: Link(1, 1, 2, 10.0, 1000.0),
            2: Link(2, 2, 3, 15.0, 1000.0),
            3: Link(3, 1, 3, 40.0, 1000.0),
        },
        demands={1: Demand(1, 1, 3, 100, CommodityType.MERCHANDISE)},
    )


def test_dijkstra_chooses_shortest_path():
    route = DijkstraRouter(instance()).shortest_path(1, 3)
    assert route is not None
    assert route.distance == 25.0
    assert route.node_ids == (1, 2, 3)


def test_greedy_seed_is_valid():
    inst = instance()
    solution = build_greedy_solution(inst, DijkstraRouter(inst))
    assert RBPValidator(inst).validate(solution).valid


def test_direct_objective():
    inst = instance()
    solution = build_greedy_solution(inst, DijkstraRouter(inst))
    objective = evaluate_direct_solution(inst, solution, DijkstraRouter(inst))
    assert objective.fixed_block == 2500.0
    assert objective.transport == 2500.0
    assert objective.total == 5000.0
