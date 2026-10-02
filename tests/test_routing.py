from jev_rbp.problem import Link, Node, RBPInstance, Settings
from jev_rbp.routing import DijkstraRouter


def test_physical_links_are_bidirectional():
    instance = RBPInstance(
        nodes={
            1: Node(node_id=1, node_type="yard"),
            2: Node(node_id=2, node_type="yard"),
        },
        links={
            10: Link(
                link_id=10,
                from_node_id=1,
                to_node_id=2,
                length=7.0,
            )
        },
        demands={},
        settings=Settings(),
    )

    route = DijkstraRouter(instance).shortest_path(2, 1)

    assert route is not None
    assert route.node_ids == (2, 1)
    assert route.link_ids == (10,)
    assert route.distance == 7.0
