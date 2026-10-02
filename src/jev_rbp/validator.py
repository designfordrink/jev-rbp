"""Independent structural validator for the Phase 3 seed solution."""

from __future__ import annotations

from .core import ValidationResult
from .problem import DIRECT_ONLY_COMMODITIES, RBPInstance, Solution


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
            expected = demand.effective_volume(self.instance.settings)
            if abs(sequence.volume - expected) > 1e-9:
                violations.append(f"demand {demand_id}: volume mismatch")

            if demand.commodity_type in DIRECT_ONLY_COMMODITIES and len(sequence.block_ids) != 1:
                violations.append(f"demand {demand_id}: direct-only commodity has multiple blocks")

            for block_id in sequence.block_ids:
                block = solution.blocks.get(block_id)
                if block is None:
                    violations.append(f"demand {demand_id}: unknown block {block_id}")
                    continue
                # Block type is intentionally separate from demand commodity type.
                # C8/full benchmark validation is responsible for commodity sharing;
                # this seed validator only checks that the block can carry the
                # demand's commodity family.
                expected_types = {
                    "Merchandise": {"Manifest"},
                    "Coal": {"Bulk"},
                    "Grain": {"Bulk"},
                    "Intermodal": {"Intermodal"},
                    "Automobile": {"Multilevel"},
                }
                if block.block_type.value not in expected_types[demand.commodity_type.value]:
                    violations.append(f"demand {demand_id}: incompatible block type")

        return ValidationResult(not violations, tuple(violations))
