"""Typed local actions used by the VLNS reproduction layer."""

from __future__ import annotations

from dataclasses import dataclass

from .core import CandidateAction
from .problem import CommodityType


@dataclass(frozen=True)
class DropAction(CandidateAction):
    """Close an existing block."""

    block_id: int = -1

    def __init__(self, block_id: int) -> None:
        super().__init__(action_type="drop", payload=(block_id,))
        object.__setattr__(self, "block_id", block_id)


@dataclass(frozen=True)
class AddAction(CandidateAction):
    """Open a new directed block."""

    from_yard_id: int = -1
    to_yard_id: int = -1
    commodity_type: CommodityType = CommodityType.MERCHANDISE

    def __init__(
        self,
        from_yard_id: int,
        to_yard_id: int,
        commodity_type: CommodityType,
    ) -> None:
        super().__init__(
            action_type="add",
            payload=(from_yard_id, to_yard_id, commodity_type.value),
        )
        object.__setattr__(self, "from_yard_id", from_yard_id)
        object.__setattr__(self, "to_yard_id", to_yard_id)
        object.__setattr__(self, "commodity_type", commodity_type)


@dataclass(frozen=True)
class SwapAction(CandidateAction):
    """Close one block and open another directed block."""

    drop_block_id: int = -1
    add_from_yard_id: int = -1
    add_to_yard_id: int = -1
    commodity_type: CommodityType = CommodityType.MERCHANDISE

    def __init__(
        self,
        drop_block_id: int,
        add_from_yard_id: int,
        add_to_yard_id: int,
        commodity_type: CommodityType,
    ) -> None:
        super().__init__(
            action_type="swap",
            payload=(
                drop_block_id,
                add_from_yard_id,
                add_to_yard_id,
                commodity_type.value,
            ),
        )
        object.__setattr__(self, "drop_block_id", drop_block_id)
        object.__setattr__(self, "add_from_yard_id", add_from_yard_id)
        object.__setattr__(self, "add_to_yard_id", add_to_yard_id)
        object.__setattr__(self, "commodity_type", commodity_type)
