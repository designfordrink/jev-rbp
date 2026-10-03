from dataclasses import dataclass

from jev_rbp.actions import AddAction, DropAction
from jev_rbp.problem import Block, BlockType, RBPInstance, Settings, Solution
from jev_rbp.rbp_selectors import RBPGreedySelector


@dataclass(frozen=True)
class Route:
    distance: float


class Router:
    def __init__(self, distances):
        self.distances = distances

    def shortest_path(self, from_yard_id, to_yard_id):
        distance = self.distances.get((from_yard_id, to_yard_id))
        return None if distance is None else Route(distance)


def make_selector():
    instance = RBPInstance(nodes={}, links={}, demands={}, settings=Settings())
    router = Router({(1, 2): 10.0, (1, 3): 100.0})
    return RBPGreedySelector(instance, router)


def test_rbp_greedy_prefers_dropping_more_expensive_block():
    selector = make_selector()
    state = Solution(
        blocks={
            1: Block(1, 1, 2, BlockType.MANIFEST, volume=100.0),
            2: Block(2, 1, 2, BlockType.MANIFEST, volume=1000.0),
        }
    )

    ranked = selector.rank(state, [DropAction(1), DropAction(2)])

    assert [action.block_id for action in ranked] == [2, 1]


def test_rbp_greedy_prefers_cheaper_add_candidate():
    selector = make_selector()
    state = Solution()

    ranked = selector.rank(
        state,
        [
            AddAction(1, 3, "Merchandise"),
            AddAction(1, 2, "Merchandise"),
        ],
    )

    assert [(action.from_yard_id, action.to_yard_id) for action in ranked] == [
        (1, 2),
        (1, 3),
    ]
