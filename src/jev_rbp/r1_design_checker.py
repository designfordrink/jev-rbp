"""R1-C controlled-instance design checker.

The checker validates cheap, design-time properties of a candidate four-file RBP
instance. It intentionally does not run the expensive VLNS/MIP experiments.

Dynamic search phenomena P1-P7 can be supplied as a machine-readable evidence
file produced by a later search audit. They are reported as NOT_EVALUATED when
no evidence file is supplied.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from heapq import heappop, heappush
from pathlib import Path
from typing import Any


DEFAULT_MIN_VOLUMES = {
    "short": 350.0,
    "medium": 700.0,
    "long": 1050.0,
}

DEMAND_TYPE_COUNTS = {
    "Merchandise": 20,
    "Coal": 10,
    "Grain": 10,
    "Intermodal": 5,
    "Automobile": 5,
}

DIRECT_ONLY = {"Intermodal", "Automobile"}

YARD_TYPE_REQUIRED = {"flat": 2, "hump": 2}


@dataclass(frozen=True)
class Check:
    name: str
    status: str  # PASS / FAIL / NOT_EVALUATED
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    required: bool = True


@dataclass
class DesignReport:
    source: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(
            check.status == "PASS"
            for check in self.checks
            if check.required
        )

    @property
    def failed(self) -> bool:
        return any(
            check.status == "FAIL"
            for check in self.checks
            if check.required
        )

    @property
    def not_evaluated(self) -> bool:
        return any(
            check.status == "NOT_EVALUATED"
            for check in self.checks
            if check.required
        )

    @property
    def status(self) -> str:
        if self.failed:
            return "FAIL"
        if self.not_evaluated:
            return "INCOMPLETE"
        return "PASS"

    def add(
        self,
        name: str,
        status: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        required: bool = True,
    ) -> None:
        self.checks.append(
            Check(
                name=name,
                status=status,
                message=message,
                details=details or {},
                required=required,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "required": check.required,
                    "message": check.message,
                    "details": check.details,
                }
                for check in self.checks
            ],
            "summary": {
                "pass": sum(c.status == "PASS" for c in self.checks),
                "fail": sum(c.status == "FAIL" for c in self.checks),
                "not_evaluated": sum(
                    c.status == "NOT_EVALUATED" for c in self.checks
                ),
            },
        }


@dataclass(frozen=True)
class InstanceTables:
    nodes: list[dict[str, str]]
    links: list[dict[str, str]]
    demands: list[dict[str, str]]
    settings: dict[str, float]


def _find_file(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [
            {str(k).strip(): str(v).strip() for k, v in row.items()}
            for row in csv.DictReader(fh)
        ]


def _column(row: dict[str, str], *names: str) -> str:
    normalized = {key.strip().lower(): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower())
        if value is not None:
            return value
    return ""


def _field_names(rows: list[dict[str, str]]) -> set[str]:
    return {key.strip().lower() for row in rows for key in row}


def _load_tables(root: Path) -> tuple[InstanceTables | None, list[str]]:
    errors: list[str] = []
    node_path = _find_file(root, ("node.csv", "nodes.csv"))
    link_path = _find_file(root, ("link.csv", "links.csv"))
    demand_path = _find_file(root, ("demand.csv", "demands.csv"))
    setting_path = _find_file(root, ("setting.csv", "settings.csv"))

    if not node_path:
        errors.append("missing node.csv/nodes.csv")
    if not link_path:
        errors.append("missing link.csv/links.csv")
    if not demand_path:
        errors.append("missing demand.csv/demands.csv")
    if not setting_path:
        errors.append("missing setting.csv/settings.csv")
    if errors:
        return None, errors

    nodes = _read_csv(node_path)
    links = _read_csv(link_path)
    demands = _read_csv(demand_path)
    setting_rows = _read_csv(setting_path)

    settings: dict[str, float] = {}
    for row in setting_rows:
        key = _column(row, "parameter", "key").strip()
        raw = _column(row, "value")
        if not key or raw == "":
            continue
        try:
            settings[key] = float(raw)
        except ValueError:
            continue

    return InstanceTables(nodes, links, demands, settings), errors


def _node_id(row: dict[str, str]) -> int:
    return int(_column(row, "node_id"))


def _link_id(row: dict[str, str]) -> int:
    return int(_column(row, "link_id"))


def _demand_type(row: dict[str, str]) -> str:
    value = _column(row, "block_type", "commodity_type")
    # A few historical files use legacy capitalization/spelling only.
    aliases = {
        "merchandise": "Merchandise",
        "coal": "Coal",
        "grain": "Grain",
        "intermodal": "Intermodal",
        "automobile": "Automobile",
    }
    return aliases.get(value.strip().lower(), value.strip())


def _settings(instance: InstanceTables) -> dict[str, float]:
    values = {key.strip(): value for key, value in instance.settings.items()}
    return {
        "min_short": values.get("min_block_vol_short(<100mi)", 350.0),
        "min_medium": values.get("min_block_vol_med(100-500mi)", 700.0),
        "min_long": values.get("min_block_vol_long(>500mi)", 1050.0),
        "ratio": values.get("max_circuitous_ratio", 1.3),
    }


def _minimum_block_volume(distance: float, settings: dict[str, float]) -> float:
    if distance < 100:
        return settings["min_short"]
    if distance <= 500:
        return settings["min_medium"]
    return settings["min_long"]


def _build_graph(
    instance: InstanceTables,
) -> tuple[dict[int, list[tuple[int, float, int]]], dict[int, tuple[int, int, float, float]]]:
    adjacency: dict[int, list[tuple[int, float, int]]] = defaultdict(list)
    links: dict[int, tuple[int, int, float, float]] = {}

    for row in instance.links:
        link_id = _link_id(row)
        u = int(_column(row, "from_node_id", "from"))
        v = int(_column(row, "to_node_id", "to"))
        length = float(_column(row, "length"))
        capacity = float(_column(row, "capacity"))
        links[link_id] = (u, v, length, capacity)
        adjacency[u].append((v, length, link_id))
        adjacency[v].append((u, length, link_id))

    return dict(adjacency), links


def _dijkstra(
    adjacency: dict[int, list[tuple[int, float, int]]],
    source: int,
    target: int,
    *,
    banned_edges: frozenset[int] = frozenset(),
) -> tuple[float, tuple[int, ...], tuple[int, ...]] | None:
    heap: list[tuple[float, int]] = [(0.0, source)]
    distance = {source: 0.0}
    previous: dict[int, tuple[int, int]] = {}

    while heap:
        cost, node = heappop(heap)
        if cost != distance[node]:
            continue
        if node == target:
            break
        for neighbor, length, link_id in adjacency.get(node, ()):
            if link_id in banned_edges:
                continue
            new_cost = cost + length
            if new_cost < distance.get(neighbor, math.inf):
                distance[neighbor] = new_cost
                previous[neighbor] = (node, link_id)
                heappush(heap, (new_cost, neighbor))

    if target not in distance:
        return None

    nodes = [target]
    links: list[int] = []
    current = target
    while current != source:
        parent, link_id = previous[current]
        nodes.append(parent)
        links.append(link_id)
        current = parent
    nodes.reverse()
    links.reverse()
    return distance[target], tuple(nodes), tuple(links)


def _second_path(
    adjacency: dict[int, list[tuple[int, float, int]]],
    shortest_links: tuple[int, ...],
    source: int,
    target: int,
) -> tuple[float, tuple[int, ...], tuple[int, ...]] | None:
    candidates = []
    for link_id in shortest_links:
        route = _dijkstra(
            adjacency,
            source,
            target,
            banned_edges=frozenset({link_id}),
        )
        if route is not None:
            candidates.append(route)
    return min(candidates, key=lambda item: item[0], default=None)


def _required_evidence_checks(evidence: dict[str, Any] | None) -> set[str]:
    required = {f"P{i}" for i in range(1, 8)}
    if evidence is None:
        return set()
    phenomena = evidence.get("phenomena", {})
    return {name for name in required if phenomena.get(name, {}).get("observed") is True}


def check_instance(
    path: str | Path,
    *,
    evidence: dict[str, Any] | None = None,
) -> DesignReport:
    root = Path(path).resolve()
    report = DesignReport(str(root))
    instance, errors = _load_tables(root)

    if instance is None:
        for error in errors:
            report.add("input_files", "FAIL", error)
        return report

    report.add("input_files", "PASS", "All four input files were found.")
    required_schemas = {
        "nodes": {
            "node_id",
            "node_type",
        },
        "links": {
            "link_id",
            "from_node_id",
            "to_node_id",
            "length",
            "capacity",
        },
        "demands": {
            "demand_id",
            "origin_yard_id",
            "dest_yard_id",
            "volume",
        },
    }
    schema_failures = []
    for name, rows in (
        ("nodes", instance.nodes),
        ("links", instance.links),
        ("demands", instance.demands),
    ):
        fields = _field_names(rows)
        if not required_schemas[name].issubset(fields):
            schema_failures.append(
                f"{name}: missing {sorted(required_schemas[name] - fields)}"
            )
    if not instance.settings:
        schema_failures.append("settings: no numeric parameters parsed")
    report.add(
        "schema",
        "FAIL" if schema_failures else "PASS",
        "; ".join(schema_failures) if schema_failures else "Required fields are present.",
        details={"errors": schema_failures},
    )

    # Identifier integrity is a basic prerequisite for every later solver audit.
    id_errors = []
    for label, rows, getter in (
        ("nodes", instance.nodes, _node_id),
        ("links", instance.links, _link_id),
        ("demands", instance.demands, lambda row: int(_column(row, "demand_id"))),
    ):
        try:
            ids = [getter(row) for row in rows]
            if len(ids) != len(set(ids)):
                id_errors.append(f"{label}: duplicate identifiers")
        except (TypeError, ValueError):
            id_errors.append(f"{label}: non-numeric identifiers")
    report.add(
        "identifier_integrity",
        "PASS" if not id_errors else "FAIL",
        "Node, link and demand identifiers are unique and numeric."
        if not id_errors
        else "; ".join(id_errors),
        details={"errors": id_errors},
    )

    yards = [
        row for row in instance.nodes
        if _column(row, "node_type").strip().lower() == "yard"
    ]
    report.add(
        "yard_count",
        "PASS" if len(yards) == 8 else "FAIL",
        f"Found {len(yards)} yards; R1-C requires exactly 8.",
        details={"yards": len(yards)},
    )

    report.add(
        "demand_count",
        "PASS" if len(instance.demands) == 50 else "FAIL",
        f"Found {len(instance.demands)} demands; R1-C requires exactly 50.",
        details={"demands": len(instance.demands)},
    )

    type_counts = Counter(_demand_type(row) for row in instance.demands)
    type_ok = type_counts == DEMAND_TYPE_COUNTS
    report.add(
        "demand_type_distribution",
        "PASS" if type_ok else "FAIL",
        "Demand type distribution matches R1-C."
        if type_ok
        else f"Expected {DEMAND_TYPE_COUNTS}, found {dict(type_counts)}.",
        details={"expected": DEMAND_TYPE_COUNTS, "actual": dict(type_counts)},
    )

    num_tracks = []
    handling_capacities = []
    handling_costs = []
    yard_types = Counter()
    railroads = set()
    interchange_count = 0
    for row in yards:
        num_tracks.append(float(_column(row, "num_tracks") or 0))
        handling_capacities.append(
            float(_column(row, "handling_capacity") or 0)
        )
        handling_costs.append(float(_column(row, "handling_cost") or 0))
        yard_types[_column(row, "yard_type").strip().lower()] += 1
        rr = _column(row, "railroad_id").strip()
        if rr:
            railroads.add(rr.upper())
        if _column(row, "is_interchange").strip().lower() in {"true", "1", "yes"}:
            interchange_count += 1

    heterogeneity_errors = []
    for label, values, minimum in (
        ("num_tracks distinct", num_tracks, 3),
        ("handling_capacity distinct", handling_capacities, 2),
        ("handling_cost distinct", handling_costs, 3),
    ):
        if len(set(values)) < minimum:
            heterogeneity_errors.append(
                f"{label}={len(set(values))}, required >= {minimum}"
            )
    for yard_type, minimum in YARD_TYPE_REQUIRED.items():
        count = sum(1 for row in yards if _column(row, "yard_type").strip().lower() == yard_type)
        if count < minimum:
            heterogeneity_errors.append(
                f"{yard_type} yards={count}, required >= {minimum}"
            )
    if len(railroads) < 2:
        heterogeneity_errors.append("fewer than 2 railroad identities")
    if interchange_count < 2:
        heterogeneity_errors.append(
            f"interchange yards={interchange_count}, required >= 2"
        )
    report.add(
        "yard_heterogeneity",
        "PASS" if not heterogeneity_errors else "FAIL",
        "Yard heterogeneity requirements are satisfied."
        if not heterogeneity_errors
        else "; ".join(heterogeneity_errors),
        details={
            "distinct_num_tracks": len(set(num_tracks)),
            "distinct_handling_capacity": len(set(handling_capacities)),
            "distinct_handling_cost": len(set(handling_costs)),
            "yard_types": dict(yard_types),
            "railroads": sorted(railroads),
            "interchange_yards": interchange_count,
        },
    )

    try:
        adjacency, links = _build_graph(instance)
    except (TypeError, ValueError, KeyError) as exc:
        report.add(
            "physical_connectivity",
            "FAIL",
            f"Physical links could not be parsed: {exc}",
        )
        return report
    yard_ids = [_node_id(row) for row in yards]
    connected = True
    if yard_ids:
        seen = {yard_ids[0]}
        stack = [yard_ids[0]]
        while stack:
            node = stack.pop()
            for neighbor, _, _ in adjacency.get(node, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        connected = set(yard_ids).issubset(seen)
    report.add(
        "physical_connectivity",
        "PASS" if connected else "FAIL",
        "The physical network connects all 8 yards."
        if connected else "At least one yard is disconnected.",
    )

    pair_distances: dict[tuple[int, int], float] = {}
    second_path_ratios: list[float] = []
    alternative_pairs = 0
    near_alternative_pairs = 0
    if connected:
        for index, source in enumerate(sorted(yard_ids)):
            for target in sorted(yard_ids)[index + 1:]:
                shortest = _dijkstra(adjacency, source, target)
                if shortest is None:
                    continue
                d1, _, shortest_links = shortest
                pair_distances[(source, target)] = d1
                second = _second_path(adjacency, shortest_links, source, target)
                if second is not None:
                    alternative_pairs += 1
                    ratio = second[0] / d1
                    second_path_ratios.append(ratio)
                    if ratio <= _settings(instance)["ratio"] + 1e-9:
                        near_alternative_pairs += 1

    cycle_rank = max(len(links) - len(yard_ids) + 1, 0)
    redundancy_ok = cycle_rank >= 2
    report.add(
        "network_redundancy",
        "PASS" if redundancy_ok else "FAIL",
        (
            "The network contains at least two independent cycle/chord structures."
            if redundancy_ok
            else f"Cycle rank is {cycle_rank}; required >= 2."
        ),
        details={"cycle_rank": cycle_rank, "links": len(links), "yards": len(yard_ids)},
    )

    alternative_ok = (
        alternative_pairs >= 6
        and near_alternative_pairs >= 3
    )
    report.add(
        "alternative_routes",
        "PASS" if alternative_ok else "FAIL",
        (
            "The network has the required number of alternative yard paths."
            if alternative_ok
            else f"Found {alternative_pairs} alternative-path pairs and "
            f"{near_alternative_pairs} within the circuitous-ratio limit; "
            "required >= 6 and >= 3."
        ),
        details={
            "alternative_pairs": alternative_pairs,
            "within_circuitous_ratio": near_alternative_pairs,
            "ratio_limit": _settings(instance)["ratio"],
        },
    )

    bands = {
        "short_lt_100": sum(1 for d in pair_distances.values() if d < 100),
        "medium_100_500": sum(1 for d in pair_distances.values() if 100 <= d <= 500),
        "long_gt_500": sum(1 for d in pair_distances.values() if d > 500),
    }
    bands_ok = all(bands.values())
    report.add(
        "distance_bands",
        "PASS" if bands_ok else "FAIL",
        "All three shortest-distance bands are represented."
        if bands_ok
        else f"Distance-band counts are {bands}; all must be non-zero.",
        details=bands,
    )

    settings = _settings(instance)
    demand_rows = []
    for row in instance.demands:
        try:
            volume = float(_column(row, "volume"))
            origin = int(_column(row, "origin_yard_id"))
            destination = int(_column(row, "dest_yard_id"))
        except ValueError:
            continue
        demand_rows.append(
            {
                "id": int(_column(row, "demand_id")),
                "origin": origin,
                "destination": destination,
                "volume": volume,
                "type": _demand_type(row),
            }
        )

    direct_errors: list[str] = []
    direct_only_count = 0
    for demand in demand_rows:
        if demand["type"] not in DIRECT_ONLY:
            continue
        direct_only_count += 1
        distance = pair_distances.get(
            tuple(sorted((demand["origin"], demand["destination"])))
        )
        required = (
            _minimum_block_volume(distance, settings)
            if distance is not None
            else math.inf
        )
        if distance is None or demand["volume"] + 1e-9 < required:
            direct_errors.append(
                f"demand {demand['id']}: volume={demand['volume']} "
                f"< direct minimum {required} or no physical path"
            )
    direct_ok = direct_only_count == 10 and not direct_errors
    report.add(
        "direct_only_demands",
        "PASS" if direct_ok else "FAIL",
        "All Intermodal/Automobile demands have feasible direct O→D blocks."
        if direct_ok
        else f"{len(direct_errors)} direct-only demand(s) fail: "
        + "; ".join(direct_errors[:5]),
        details={
            "direct_only_count": direct_only_count,
            "errors": direct_errors,
        },
    )

    od_volume_by_type: dict[tuple[int, int, str], float] = defaultdict(float)
    od_total: dict[tuple[int, int], float] = defaultdict(float)
    for demand in demand_rows:
        key = (demand["origin"], demand["destination"], demand["type"])
        od_volume_by_type[key] += demand["volume"]
        od_total[(demand["origin"], demand["destination"])] += demand["volume"]

    def segment_supported(
        origin: int,
        destination: int,
        commodity_type: str,
    ) -> bool:
        distance = pair_distances.get(tuple(sorted((origin, destination))))
        if distance is None:
            return False
        volume = od_volume_by_type.get((origin, destination, commodity_type), 0.0)
        return volume + 1e-9 >= _minimum_block_volume(distance, settings)

    direct_markets = 0
    consolidation_markets = 0
    competing_hub_demands = 0
    for demand in demand_rows:
        if demand["type"] in DIRECT_ONLY or demand["origin"] == demand["destination"]:
            continue
        distance = pair_distances.get(
            tuple(sorted((demand["origin"], demand["destination"])))
        )
        if distance is None:
            continue
        if od_volume_by_type[
            demand["origin"], demand["destination"], demand["type"]
        ] + 1e-9 >= _minimum_block_volume(distance, settings):
            direct_markets += 1

        hubs = []
        for hub in yard_ids:
            if hub in (demand["origin"], demand["destination"]):
                continue
            if segment_supported(demand["origin"], hub, demand["type"]) and segment_supported(
                hub, demand["destination"], demand["type"]
            ):
                hubs.append(hub)
        if (
            od_volume_by_type[
                demand["origin"], demand["destination"], demand["type"]
            ]
            < _minimum_block_volume(distance, settings)
            and hubs
        ):
            consolidation_markets += 1
        if len(hubs) >= 2:
            competing_hub_demands += 1

    report.add(
        "demand_market_structure",
        "PASS"
        if direct_markets > 0 and consolidation_markets > 0 and competing_hub_demands >= 4
        else "FAIL",
        (
            "Direct, consolidation and competing-hub demand structures are present."
            if direct_markets > 0 and consolidation_markets > 0 and competing_hub_demands >= 4
            else f"Need direct_markets>0, consolidation_markets>0, "
            f"competing_hub_demands>=4; found {direct_markets}, "
            f"{consolidation_markets}, {competing_hub_demands}."
        ),
        details={
            "direct_markets": direct_markets,
            "consolidation_markets": consolidation_markets,
            "competing_hub_demands": competing_hub_demands,
        },
    )

    # Estimate physical and handling pressure from demand shortest paths. This is
    # deliberately an early design-time proxy, not a replacement for C5/C3 exact
    # evaluation. It answers whether the input contains plausible bottlenecks.
    link_load = defaultdict(float)
    yard_classification_pressure = defaultdict(float)
    yard_by_id = {_node_id(row): row for row in yards}
    for demand in demand_rows:
        route = _dijkstra(adjacency, demand["origin"], demand["destination"])
        if route is None:
            continue
        _, path_nodes, path_links = route
        for link_id in path_links:
            link_load[link_id] += demand["volume"]
        for node in path_nodes[1:-1]:
            if node in yard_by_id:
                yard_classification_pressure[node] += demand["volume"]

    utilization = {}
    for link_id, load in link_load.items():
        capacity = links[link_id][3]
        utilization[link_id] = load / capacity if capacity > 0 else math.inf
    top_link_util = sorted(utilization.values(), reverse=True)
    potential_link_bottlenecks = sum(value >= 0.5 for value in top_link_util)
    yard_utilization = {}
    for yard_id, pressure in yard_classification_pressure.items():
        capacity = float(_column(yard_by_id[yard_id], "handling_capacity") or 0)
        yard_utilization[yard_id] = pressure / capacity if capacity > 0 else math.inf
    potential_yard_bottlenecks = sum(value >= 0.5 for value in yard_utilization.values())
    bottleneck_ok = potential_link_bottlenecks >= 2 and potential_yard_bottlenecks >= 2
    report.add(
        "potential_bottlenecks",
        "PASS" if bottleneck_ok else "FAIL",
        (
            "Demand-weighted shortest-path proxy exposes at least two physical-link "
            "and two yard bottlenecks."
            if bottleneck_ok
            else f"Found {potential_link_bottlenecks} link and "
            f"{potential_yard_bottlenecks} yard bottleneck candidates; required >= 2 each."
        ),
        details={
            "top_link_utilizations": top_link_util[:5],
            "yard_utilizations": dict(sorted(
                yard_utilization.items(), key=lambda item: item[1], reverse=True
            )[:5]),
            "threshold": 0.5,
            "note": "Design-time proxy only; exact C3/C5 validation remains authoritative.",
        },
    )

    evidence_map = evidence.get("phenomena", {}) if evidence else {}
    for i in range(1, 8):
        name = f"P{i}"
        item = evidence_map.get(name)
        if item is None:
            report.add(
                name,
                "NOT_EVALUATED",
                "Dynamic search evidence was not supplied.",
                required=True,
            )
        elif item.get("observed") is True:
            report.add(
                name,
                "PASS",
                item.get("summary", f"{name} observed in search evidence."),
                details=item,
            )
        else:
            report.add(
                name,
                "FAIL",
                item.get("summary", f"{name} not observed."),
                details=item,
            )

    return report


def _print_report(report: DesignReport, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"R1-C design check: {report.status}")
        for check in report.checks:
            flag = {"PASS": "✓", "FAIL": "✗", "NOT_EVALUATED": "?"}[check.status]
            suffix = "" if check.required else " (advisory)"
            print(f"{flag} {check.name}{suffix}: {check.message}")
        summary = report.to_dict()["summary"]
        print(
            f"Summary: PASS={summary['pass']} FAIL={summary['fail']} "
            f"NOT_EVALUATED={summary['not_evaluated']}"
        )
    return 0 if report.status == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    evidence = None
    if args.evidence:
        with args.evidence.open(encoding="utf-8") as fh:
            evidence = json.load(fh)

    return _print_report(
        check_instance(args.instance, evidence=evidence),
        as_json=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
