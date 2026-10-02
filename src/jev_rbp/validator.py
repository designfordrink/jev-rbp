"""Independent structural validator for the Phase 3 seed solution."""

from __future__ import annotations

from .core import ValidationResult
from .problem import CommodityType, RBPInstance, Solution


class RBPValidator:
    def __init__(self, instance: RBPInstance) -> None:
        self.instance = instance

    def validate(self, solution: Solution) -> ValidationResult:
        violations = []
        for demand_id, demand in self.instance.demands.items():
            sequence = solution.sequences.get(demand_id)
            if sequence is None:
                violations.append(f"demand {demand_id}: missing blocking sequence")
                continue
            expected = demand.volume * self.instance.settings.demand_multiplier
            if abs(sequence.volume - expected) > 1e-9:
                violations.append(f"demand {demand_id}: volume mismatch")
            if demand.commodity_type in {CommodityType.INTERMODAL, CommodityType.AUTOMOBILE}:
                if len(sequence.block_ids) != 1:
                    violations.append(f"demand {demand_id}: direct-only commodity has multiple blocks")
            for block_id in sequence.block_ids:
                block = solution.blocks.get(block_id)
                if block is None:
                    violations.append(f"demand {demand_id}: unknown block {block_id}")
                    continue
                if block.commodity_type != demand.commodity_type:
                    violations.append(f"demand {demand_id}: commodity mismatch")
        return ValidationResult(not violations, tuple(violations))
