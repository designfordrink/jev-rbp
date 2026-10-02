from jev_rbp.actions import DropAction
from jev_rbp.selectors import IdentitySelector, RandomSelector


def test_identity_selector_preserves_order():
    candidates = [DropAction(1), DropAction(2), DropAction(3)]
    assert IdentitySelector().rank(None, candidates) == candidates


def test_random_selector_is_reproducible():
    candidates = [DropAction(1), DropAction(2), DropAction(3)]
    assert RandomSelector(seed=42).rank(None, candidates) == RandomSelector(seed=42).rank(
        None, candidates
    )
