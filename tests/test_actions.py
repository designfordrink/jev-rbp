from jev_rbp.actions import AddAction, DropAction, SwapAction
from jev_rbp.problem import CommodityType


def test_drop_action_payload():
    action = DropAction(7)
    assert action.action_type == "drop"
    assert action.payload == (7,)
    assert action.block_id == 7


def test_add_action_is_directional():
    action = AddAction(1, 2, CommodityType.COAL)
    assert action.action_type == "add"
    assert action.payload == (1, 2, "Coal")


def test_swap_action_payload():
    action = SwapAction(7, 1, 2, CommodityType.GRAIN)
    assert action.payload == (7, 1, 2, "Grain")
