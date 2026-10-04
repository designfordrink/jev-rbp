from jev_rbp.actions import AddAction
from jev_rbp.moves import MoveContext, RBPMoveGenerator
from jev_rbp.problem import CommodityType, Demand, Link, Node, RBPInstance, Settings
from jev_rbp.routing import DijkstraRouter


def test_candidate_generator_preserves_commodity_type():
    instance = RBPInstance(
        nodes={
            1: Node(1, "yard"),
            2: Node(2, "yard"),
        },
        links={1: Link(1, 1, 2, 10.0, 1000.0)},
        demands={1: Demand(1, 1, 2, 100, CommodityType.GRAIN)},
        settings=Settings(),
    )
    generator = RBPMoveGenerator(MoveContext(instance, DijkstraRouter(instance)))

    actions = generator.generate_phase(__import__("jev_rbp.problem", fromlist=["Solution"]).Solution(), "add")

    assert len(actions) == 2
    assert all(isinstance(action, AddAction) for action in actions)
    assert {action.commodity_type for action in actions} == {CommodityType.GRAIN}
