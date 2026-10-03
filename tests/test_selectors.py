from jev_rbp.actions import AddAction, DropAction
from jev_rbp.problem import CommodityType
from jev_rbp.selectors import GreedySelector, IdentitySelector, RandomSelector


def test_identity_selector_preserves_order():
    candidates = [DropAction(1), DropAction(2), DropAction(3)]
    assert IdentitySelector().rank(None, candidates) == candidates


def test_random_selector_is_reproducible():
    candidates = [DropAction(1), DropAction(2), DropAction(3)]
    assert RandomSelector(seed=42).rank(None, candidates) == RandomSelector(seed=42).rank(
        None, candidates
    )


def test_greedy_selector_ranks_by_cheap_score():
    candidates = [
        DropAction(10),
        DropAction(2),
        DropAction(7),
    ]

    selector = GreedySelector(
        lambda state, action: {10: 3.0, 2: 1.0, 7: 2.0}[action.block_id]
    )

    ranked = selector.rank(object(), candidates)

    assert [action.block_id for action in ranked] == [2, 7, 10]


def test_greedy_selector_is_stable_for_equal_scores():
    candidates = [
        AddAction(1, 2, CommodityType.MERCHANDISE),
        AddAction(1, 3, CommodityType.MERCHANDISE),
    ]

    selector = GreedySelector(lambda state, action: 0.0)

    ranked = selector.rank(object(), candidates)

    assert ranked == candidates
