"""Independent RAS v2.0 benchmark authority.

This module is deliberately separate from VLNS/JEV.  It validates a complete
solution against the public benchmark rules and computes operating cost plus
Stress Score.  It does not use solver decisions to decide feasibility.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from math import inf, isfinite

from .problem import DIRECT_ONLY_COMMODITIES, RBPInstance, Solution
from .routing import DijkstraRouter


CLASSIFICATION_BLOCK_TYPES = frozenset({"Manifest", "Bulk"})
CLASS_I_RAILROADS = frozenset({"BNSF", "CN", "CSX", "UP", "NS", "CPKC"})


@dataclass(frozen=True)
class BenchmarkCost:
    fixed: float
    transport: float
    handling: float
    interchange: float
    total: float
    total_car_miles: float


@dataclass(frozen=True)
class StressMetrics:
    penalty_coefficient: float
    total_demand_cars: float
    served_demand_cars: float
    unserved_demand_cars: float
    loaded_ratio: float
    unserved_car_miles: float
    stress_score: float


@dataclass
class BenchmarkReport:
    feasible: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cost: BenchmarkCost | None = None
    stress: StressMetrics | None = None
    checks: dict[str, int | float | bool] = field(default_factory=dict)

    def add_violation(self, message: str) -> None:
        self.feasible = False
        self.violations.append(message)


class BenchmarkAuthority:
    """Independent implementation of the released RAS v2.0 checks."""

    def __init__(self, instance: RBPInstance) -> None:
        self.instance = instance
        self.router = DijkstraRouter(instance)

    def validate(self, solution: Solution) -> BenchmarkReport:
        report = BenchmarkReport()
        self._check_flow(solution, report)
        self._check_no_subtour(solution, report)
        self._check_track_limits(solution, report)
        self._check_handling_capacity(solution, report)

        actual_volumes = self._actual_block_volumes(solution)
        distances = self._route_distances(solution, report)

        self._check_min_block_volume(solution, actual_volumes, report)
        self._check_link_capacity(solution, actual_volumes, report)
        self._check_circuitous_ratio(solution, distances, report)
        self._check_single_path(solution, report)
        self._check_blocking_rule(solution, report)
        self._check_direct_block_rule(solution, report)
        self._check_demand_volume_consistency(solution, report)

        report.cost = self.evaluate_cost(solution, actual_volumes, distances)
        report.stress = self.evaluate_stress(solution)

        return report

    def evaluate_cost(
        self,
        solution: Solution,
        actual_volumes: dict[int, float] | None = None,
        distances: dict[int, float] | None = None,
    ) -> BenchmarkCost:
        actual_volumes = actual_volumes or self._actual_block_volumes(solution)
        distances = distances or self._route_distances(solution, BenchmarkReport())

        fixed = len(solution.blocks) * self.instance.settings.block_fixed_cost
        transport = 0.0
        total_car_miles = 0.0

        for block_id, block in solution.blocks.items():
            volume = actual_volumes.get(block_id, 0.0)
            distance = distances.get(block_id, 0.0)
            car_miles = volume * distance
            total_car_miles += car_miles
            transport += (
                car_miles * self.instance.settings.transport_cost_coefficient
            )

        handling = 0.0
        for sequence in solution.sequences.values():
            for block_id in sequence.block_ids[:-1]:
                block = solution.blocks.get(block_id)
                if block is not None:
                    handling += (
                        sequence.volume
                        * self.instance.nodes[block.to_yard_id].handling_cost
                    )

        interchange = 0.0
        for block_id, volume in actual_volumes.items():
            if volume <= 0:
                continue
            block = solution.blocks.get(block_id)
            if block is None:
                continue
            origin_rr = _class_i_railroad(
                self.instance.nodes[block.from_yard_id].railroad_id
            )
            dest_rr = _class_i_railroad(
                self.instance.nodes[block.to_yard_id].railroad_id
            )
            if origin_rr and dest_rr and origin_rr != dest_rr:
                interchange += volume * self.instance.settings.interchange_cost

        total = fixed + transport + handling + interchange
        return BenchmarkCost(
            fixed=fixed,
            transport=transport,
            handling=handling,
            interchange=interchange,
            total=total,
            total_car_miles=total_car_miles,
        )

    def evaluate_stress(self, solution: Solution) -> StressMetrics:
        served_by_demand = defaultdict(float)
        for sequence in solution.sequences.values():
            if sequence.volume > 0:
                served_by_demand[sequence.demand_id] += sequence.volume

        total = 0.0
        served = 0.0
        unserved_car_miles = 0.0

        for demand_id, demand in self.instance.demands.items():
            volume = demand.effective_volume(self.instance.settings)
            served_volume = min(
                max(served_by_demand.get(demand_id, 0.0), 0.0),
                volume,
            )
            unserved = max(volume - served_volume, 0.0)
            total += volume
            served += served_volume

            if unserved:
                route = self.router.shortest_path(
                    demand.origin_yard_id, demand.dest_yard_id
                )
                if route is None:
                    raise ValueError(
                        "Cannot compute Stress Score: no physical shortest path "
                        f"for demand {demand_id}"
                    )
                unserved_car_miles += unserved * route.distance

        loaded_ratio = served / total if total else 1.0
        return StressMetrics(
            penalty_coefficient=self.instance.settings.stress_penalty_m,
            total_demand_cars=total,
            served_demand_cars=served,
            unserved_demand_cars=total - served,
            loaded_ratio=loaded_ratio,
            unserved_car_miles=unserved_car_miles,
            stress_score=(
                (self.evaluate_cost(solution).total)
                + self.instance.settings.stress_penalty_m * unserved_car_miles
            ),
        )

    def _check_flow(self, solution: Solution, report: BenchmarkReport) -> None:
        for demand_id, demand in self.instance.demands.items():
            sequence = solution.sequences.get(demand_id)
            if sequence is None:
                report.add_violation(
                    f"C1: demand {demand_id} has no blocking sequence"
                )
                continue
            if not sequence.block_ids:
                report.add_violation(
                    f"C1: demand {demand_id} has an empty blocking sequence"
                )
                continue

            first = solution.blocks.get(sequence.block_ids[0])
            last = solution.blocks.get(sequence.block_ids[-1])
            if first is None or last is None:
                report.add_violation(
                    f"C1: demand {demand_id} references a missing block"
                )
                continue

            if first.from_yard_id != demand.origin_yard_id:
                report.add_violation(
                    f"C1: demand {demand_id} starts at {first.from_yard_id}, "
                    f"expected {demand.origin_yard_id}"
                )
            if last.to_yard_id != demand.dest_yard_id:
                report.add_violation(
                    f"C1: demand {demand_id} ends at {last.to_yard_id}, "
                    f"expected {demand.dest_yard_id}"
                )

            for left, right in zip(sequence.block_ids, sequence.block_ids[1:]):
                b1 = solution.blocks.get(left)
                b2 = solution.blocks.get(right)
                if b1 is None or b2 is None:
                    continue
                if b1.to_yard_id != b2.from_yard_id:
                    report.add_violation(
                        f"C1: demand {demand_id} chain breaks between "
                        f"blocks {left} and {right}"
                    )

        for block_id, route in solution.routes.items():
            block = solution.blocks.get(block_id)
            if block is None:
                report.add_violation(
                    f"C1: route references unknown block {block_id}"
                )
                continue
            if not route.node_ids or not route.link_ids:
                continue
            if route.node_ids[0] != block.from_yard_id:
                report.add_violation(
                    f"C1: route {block_id} starts at {route.node_ids[0]}, "
                    f"expected {block.from_yard_id}"
                )
            if route.node_ids[-1] != block.to_yard_id:
                report.add_violation(
                    f"C1: route {block_id} ends at {route.node_ids[-1]}, "
                    f"expected {block.to_yard_id}"
                )
            if len(route.link_ids) != len(route.node_ids) - 1:
                report.add_violation(
                    f"C1: route {block_id} has inconsistent node/link counts"
                )
            if len(route.node_ids) != len(set(route.node_ids)):
                report.add_violation(
                    f"C1: route {block_id} contains a physical subtour"
                )

            for i, link_id in enumerate(route.link_ids):
                link = self.instance.links.get(link_id)
                if link is None:
                    report.add_violation(
                        f"C1: route {block_id} references unknown link {link_id}"
                    )
                    continue
                u, v = route.node_ids[i], route.node_ids[i + 1]
                if {link.from_node_id, link.to_node_id} != {u, v}:
                    report.add_violation(
                        f"C1: route {block_id} link {link_id} does not match "
                        f"nodes {u}->{v}"
                    )

    def _check_no_subtour(self, solution: Solution, report: BenchmarkReport) -> None:
        for demand_id, sequence in solution.sequences.items():
            yards: list[int] = []
            for block_id in sequence.block_ids:
                block = solution.blocks.get(block_id)
                if block is None:
                    continue
                if not yards:
                    yards.append(block.from_yard_id)
                yards.append(block.to_yard_id)
            if len(yards) != len(set(yards)):
                report.add_violation(
                    f"C1b: demand {demand_id} revisits a yard: {yards}"
                )

    def _check_track_limits(self, solution: Solution, report: BenchmarkReport) -> None:
        outgoing = defaultdict(int)
        for block in solution.blocks.values():
            if block.block_type.value in CLASSIFICATION_BLOCK_TYPES:
                outgoing[block.from_yard_id] += 1
        for yard_id, count in outgoing.items():
            limit = self.instance.nodes[yard_id].num_tracks
            if count > limit:
                report.add_violation(
                    f"C2: yard {yard_id} has {count} classification blocks "
                    f"but only {limit} tracks"
                )

    def _check_handling_capacity(
        self, solution: Solution, report: BenchmarkReport
    ) -> None:
        classified = defaultdict(float)
        for sequence in solution.sequences.values():
            for block_id in sequence.block_ids[:-1]:
                block = solution.blocks.get(block_id)
                if block is not None:
                    classified[block.to_yard_id] += sequence.volume

        for yard_id, volume in classified.items():
            capacity = self.instance.nodes[yard_id].handling_capacity
            if volume > capacity:
                report.add_violation(
                    f"C3: yard {yard_id} handles {volume} cars over capacity "
                    f"{capacity}"
                )

    def _check_min_block_volume(
        self,
        solution: Solution,
        actual_volumes: dict[int, float],
        report: BenchmarkReport,
    ) -> None:
        for block_id, volume in actual_volumes.items():
            if volume <= 0:
                continue
            block = solution.blocks[block_id]
            route = self.router.shortest_path(block.from_yard_id, block.to_yard_id)
            if route is None:
                report.add_violation(
                    f"C4: block {block_id} has no physical shortest path"
                )
                continue
            required = _minimum_block_volume(
                route.distance, self.instance
            )
            if volume + 1e-6 < required:
                report.add_violation(
                    f"C4: block {block_id} volume {volume} < {required}"
                )

    def _check_link_capacity(
        self,
        solution: Solution,
        actual_volumes: dict[int, float],
        report: BenchmarkReport,
    ) -> None:
        link_flow = defaultdict(float)
        for block_id, volume in actual_volumes.items():
            route = solution.routes.get(block_id)
            if route is None:
                continue
            for link_id in route.link_ids:
                link_flow[link_id] += volume

        for link_id, volume in link_flow.items():
            link = self.instance.links.get(link_id)
            if link is None:
                continue
            if volume > link.capacity:
                report.add_violation(
                    f"C5: link {link_id} carries {volume} cars > capacity "
                    f"{link.capacity}"
                )

    def _check_circuitous_ratio(
        self,
        solution: Solution,
        distances: dict[int, float],
        report: BenchmarkReport,
    ) -> None:
        for block_id, distance in distances.items():
            block = solution.blocks[block_id]
            shortest = self.router.shortest_path(
                block.from_yard_id, block.to_yard_id
            )
            if shortest is None or shortest.distance <= 0:
                report.add_violation(
                    f"C6: no finite shortest path for block {block_id}"
                )
                continue
            if (
                distance
                > shortest.distance * self.instance.settings.max_circuitous_ratio
                + 1e-4
            ):
                report.add_violation(
                    f"C6: block {block_id} circuity {distance / shortest.distance:.4f} "
                    f"> {self.instance.settings.max_circuitous_ratio}"
                )

    def _check_single_path(self, solution: Solution, report: BenchmarkReport) -> None:
        seen: dict[tuple[int, str], set[tuple[int, ...]]] = defaultdict(set)
        for sequence in solution.sequences.values():
            demand = self.instance.demands.get(sequence.demand_id)
            if demand is None:
                continue
            key = (sequence.demand_id, demand.commodity_type.value)
            seen[key].add(sequence.block_ids)
        for key, paths in seen.items():
            if len(paths) > 1:
                report.add_violation(
                    f"C7: demand {key[0]} has multiple blocking paths"
                )

    def _check_blocking_rule(self, solution: Solution, report: BenchmarkReport) -> None:
        block_type: dict[int, str] = {}
        for sequence in solution.sequences.values():
            demand = self.instance.demands.get(sequence.demand_id)
            if demand is None:
                continue
            commodity_type = demand.commodity_type.value
            for block_id in sequence.block_ids:
                previous = block_type.get(block_id)
                if previous is not None and previous != commodity_type:
                    report.add_violation(
                        f"C8: block {block_id} carries both {previous} and "
                        f"{commodity_type}"
                    )
                block_type[block_id] = commodity_type

    def _check_direct_block_rule(
        self, solution: Solution, report: BenchmarkReport
    ) -> None:
        for demand_id, demand in self.instance.demands.items():
            if demand.commodity_type not in DIRECT_ONLY_COMMODITIES:
                continue
            sequence = solution.sequences.get(demand_id)
            if sequence is None:
                continue
            if len(sequence.block_ids) != 1:
                report.add_violation(
                    f"C9: direct-only demand {demand_id} uses "
                    f"{len(sequence.block_ids)} blocks"
                )
                continue
            block = solution.blocks.get(sequence.block_ids[0])
            if block is None:
                continue
            if (
                block.from_yard_id != demand.origin_yard_id
                or block.to_yard_id != demand.dest_yard_id
            ):
                report.add_violation(
                    f"C9: direct-only demand {demand_id} block is not its OD"
                )

    def _check_demand_volume_consistency(
        self, solution: Solution, report: BenchmarkReport
    ) -> None:
        tol = 1e-6
        submitted = defaultdict(float)

        for demand_id, sequence in solution.sequences.items():
            if sequence.volume <= tol:
                report.add_violation(
                    f"C9b: demand {demand_id} has non-positive sequence volume"
                )
            submitted[demand_id] += sequence.volume

            demand = self.instance.demands.get(demand_id)
            if demand is None:
                report.add_violation(
                    f"C9b: unknown demand {demand_id}"
                )
                continue

            expected = demand.effective_volume(self.instance.settings)
            if sequence.volume > expected + tol:
                report.add_violation(
                    f"C9b: demand {demand_id} overserved by "
                    f"{sequence.volume - expected}"
                )

        for demand_id, volume in submitted.items():
            demand = self.instance.demands.get(demand_id)
            if demand is not None and volume > demand.effective_volume(
                self.instance.settings
            ) + tol:
                report.add_violation(
                    f"C9b: demand {demand_id} total transported volume exceeds demand"
                )

    def _actual_block_volumes(self, solution: Solution) -> dict[int, float]:
        volumes = defaultdict(float)
        for sequence in solution.sequences.values():
            for block_id in sequence.block_ids:
                volumes[block_id] += sequence.volume
        return dict(volumes)

    def _route_distances(
        self, solution: Solution, report: BenchmarkReport
    ) -> dict[int, float]:
        distances = {}
        for block_id, block in solution.blocks.items():
            route = solution.routes.get(block_id)
            if route is None or not route.link_ids:
                shortest = self.router.shortest_path(
                    block.from_yard_id, block.to_yard_id
                )
                if shortest is None:
                    report.add_violation(
                        f"C1: block {block_id} has no physical route"
                    )
                    distances[block_id] = inf
                else:
                    distances[block_id] = shortest.distance
                continue

            distance = 0.0
            for link_id in route.link_ids:
                link = self.instance.links.get(link_id)
                if link is None:
                    report.add_violation(
                        f"C1: block {block_id} references unknown link {link_id}"
                    )
                    continue
                distance += link.length
            distances[block_id] = distance
        return distances


def _minimum_block_volume(distance: float, instance: RBPInstance) -> float:
    settings = instance.settings
    if distance < 100:
        return settings.min_block_vol_short
    if distance <= 500:
        return settings.min_block_vol_medium
    return settings.min_block_vol_long


def _class_i_railroad(value: str) -> str:
    label = str(value or "").strip().upper()
    if label == "CSXT":
        label = "CSX"
    return label if label in CLASS_I_RAILROADS else ""


def benchmark_validate(
    instance: RBPInstance, solution: Solution
) -> BenchmarkReport:
    """Convenience wrapper for the independent benchmark authority."""
    return BenchmarkAuthority(instance).validate(solution)
