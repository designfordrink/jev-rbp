# Phase 3A — RAS v2.1 Public Benchmark Archaeology

## Purpose

Phase 3A freezes the externally observable RAS v2.1 benchmark contract before changing the JEV-RBP internal model.

The official Kaggle competition dataset is invite/participant gated. For research and reproducibility, JEV-RBP uses the public ASU Trans+AI Lab mirror:

- Repository: https://github.com/asu-trans-ai-lab/RAS2026-PSC
- Release: v2.1
- Scoring/validator package: v2.0
- Official competition sources remain Kaggle and INFORMS RAS.

The public release contains the schemas, validator, scoring code, input CSVs, OD distance matrix archive, and nine sample solution JSON files.

## 1. Benchmark layers

The release defines three network-resolution layers:

| Layer | Published design origins | Published OD pairs | Archived v2.1 demand rows |
|---|---:|---:|---:|
| L1 | 21 | 411 | 2,044 |
| L2 | 132 | 11,897 | 2,044 |
| L3 | 1,041 | 136,677 | 2,427 |

All layers share the 47,193-node / 106,570-link physical network in the archived package.

**Important:** the published layer-design table and the archived v2.1 CSV statistics are not identical. In particular, the archived L1 demand file contains the same 2,044-row population as L2. JEV-RBP must record both the benchmark layer label and the exact dataset snapshot used for an experiment.

## 2. Input contract

### node.csv

Required schema fields:

- `node_id`
- `node_type`
- `x_coord`
- `y_coord`

Relevant yard fields:

- `name`
- `yard_type`
- `yard_level`
- `railroad_id`
- `num_tracks`
- `handling_capacity`
- `handling_cost`
- `is_interchange`
- `allowed_commodities`
- `allowed_traversal`
- `datasource`

Only `node_type=yard` nodes are demand endpoints/classification points.

### link.csv

Required:

- `link_id`
- `from_node_id`
- `to_node_id`
- `length`
- `capacity`

Additional:

- `railroad_id`
- `free_speed`
- `tracks`
- `geometry`

The physical network is represented as links. The public validator treats the physical connectivity as bidirectional when constructing fallback shortest paths, even though CSV records themselves have from/to direction.

### demand.csv

Required:

- `demand_id`
- `origin_yard_id`
- `dest_yard_id`
- `volume`
- `block_type`

The five demand commodity labels are:

- Merchandise
- Intermodal
- Coal
- Grain
- Automobile

The field is named `block_type` in the input schema, although semantically it identifies the commodity-derived demand class.

### setting.csv

Canonical parameters:

- `min_block_vol_short(<100mi)`
- `min_block_vol_med(100-500mi)`
- `min_block_vol_long(>500mi)`
- `max_circuitous_ratio`
- `operating_cycle`
- `block_fixed_cost`
- `transport_cost_coefficient`
- `interchange_cost`
- `stress_penalty_M`
- `demand_multiplier`

The scenario multiplier is applied to demand volume at validation/scoring time.

## 3. Solution contract

The solution JSON has exactly two top-level sections:

```text
inputs
outputs
```

`inputs` contains a reproducibility copy of settings, nodes, links and demands.

`outputs` contains three coupled decisions:

```text
1 Block Design
2 Blocking Sequence
3 Block Route
```

### 3.1 Block Design

Each opened block contains:

- `block_id`
- `from_yard_id`
- `to_yard_id`
- `block_volume`
- `block_type` (canonical v1.5 field)
- `commodity_type` may also appear for compatibility.

**Critical distinction:** block type is NOT the same enumeration as demand commodity type.

Block categories are:

- Manifest
- Bulk
- Intermodal
- Multilevel

The validator uses `block_type` for the classification-track rule.

### 3.2 Blocking Sequence

Each demand routing record contains:

- `commodity_id`
- `commodity_type`
- `origin_yard_id`
- `dest_yard_id`
- `volume`
- `blocking_sequence`

The sequence is a string:

```text
6
6 -> 12
6 -> 12 -> 31
```

The sequence is a path through the **block service graph**, not a physical-node path.

### 3.3 Block Route

Each opened block has:

- `block_id`
- `from_yard_id`
- `to_yard_id`
- `physical_path_nodes`
- `physical_path_links`

The physical path is stored as arrow-separated strings.

Therefore the benchmark explicitly separates:

```text
commodity routing
    ↓
block IDs

block movement
    ↓
physical node/link path
```

This distinction is fundamental for implementing Drop/Add/Swap correctly.

## 4. Validator contract

The public v2.0 validator implements the following checks.

### C1 — Flow conservation

For every blocking sequence:

- first block starts at the commodity origin;
- last block ends at the commodity destination;
- consecutive blocks connect: destination of block i = origin of block i+1;
- referenced blocks must exist;
- supplied physical paths must have matching endpoints and existing physical edges.

### C1b — No subtour

A blocking sequence may not revisit a yard.

Example:

```text
A -> B -> C -> B
```

is invalid.

### C2 — Yard track limit

Only classification block types count:

```text
manifest
coal
grain
```

Intermodal and Multilevel do not consume this classification-track budget.

The number of outbound classification blocks from a yard is compared with `num_tracks`.

### C3 — Yard handling capacity

Handling is charged only at intermediate classification yards in a multi-block sequence.

For a sequence:

```text
A -> B -> C
```

the flow entering B is classified/handled at B; endpoint pass-through is not treated as intermediate handling.

### C4 — Minimum block volume

The minimum block volume depends on the shortest physical distance between the block endpoints:

- <100 mi → 350
- 100–500 mi → 700
- >500 mi → 1050

The validator calculates this from the shared shortest-path service.

### C5 — Link capacity

Physical link flow is accumulated from the submitted block routes and their actual transported volumes.

### C6 — Maximum circuitous ratio

For every used block:

```text
actual block route distance
-------------------------------- <= 1.3
shortest physical distance
```

The shortest-distance source is the OD matrix first, then sparse Dijkstra fallback.

### C7 — Single-path uniqueness

A commodity may not be split across multiple blocking sequences.

### C8 — Single commodity type per block

One block cannot be used by different commodity types.

### C9 — Direct-block rule

Intermodal and Automobile must use a single direct origin-to-destination block.

### C9b — Demand-volume consistency

Submitted transported volume:

- must be positive;
- must reference a known demand;
- must match demand origin/destination;
- must not exceed demand volume.

Under-served demand is allowed and contributes to the stress penalty.

## 5. Objective

Operating cost is:

```text
fixed block cost
+ transportation cost
+ handling cost
+ interchange cost
```

### Fixed

```#blocks × block_fixed_cost
```

### Transportation

For each used block:

```transported cars × physical block-route miles × transport_cost_coefficient
```

### Handling

Intermediate classification-yard volume × that yard's `handling_cost`.

### Interchange

v2.0 uses a **per-block two-endpoint Class-I-only rule**:

- compare the origin-yard railroad and destination-yard railroad of each used block;
- charge one interchange when both are recognized Class-I railroads and they differ;
- intermediate physical path nodes are ignored;
- `CSXT` is normalized to `CSX`.

This is important because it differs from counting every railroad transition along the physical path.

## 6. Stress Score

Unserved demand is allowed.

The validator computes:

```text
Stress Score =
    operating cost
    + M × unserved car-miles
```

where `M = stress_penalty_M`, default 5.

Unserved car-miles use the shortest physical OD distance, not the submitted block route.

## 7. Shortest-path convention

The public validator uses one shared shortest-path convention:

1. supplied `od_distance_matrix.csv`;
2. sparse Dijkstra on the physical network for missing pairs.

The OD matrix is directional: `u -> v` and `v -> u` are separate records.

JEV-RBP should therefore not maintain separate inconsistent distance calculations for:

- minimum block volume;
- circuitous ratio;
- stress score;
- candidate generation.

## 8. Sample solutions

The v2.1 release contains nine sample solution JSON files:

```text
L1/L2/L3 × demand multiplier 0.5/1.0/2.0
```

The repository's release documentation identifies these as:

```text
scoring/sample_solutions/
solution_result_l{level}_{scale}.json
```

The sample solutions are benchmark artifacts for schema/validator/scoring inspection, not claimed global optima.

## 9. Consequences for JEV-RBP

The current internal model has several deliberate mismatches that must be corrected in the next phase.

### Current mismatch A — Block commodity type

Current JEV-RBP uses:

```text
Block.commodity_type = CommodityType
```

The benchmark requires a distinction between:

```text
Demand commodity:
Merchandise / Intermodal / Coal / Grain / Automobile

Block type:
Manifest / Bulk / Intermodal / Multilevel
```

This distinction is required by C2 and C8.

### Current mismatch B — Demand volume

Current `Demand.volume` is integer-only.

The schema declares volume as numeric, and scenario scaling can make it non-integer.

The internal model should therefore use `float` (or a documented numeric abstraction).

### Current mismatch C — Input metadata

Current `Node` omits coordinates and several benchmark metadata fields.

This is acceptable for the seed prototype but not for a faithful v2.1 model.

### Current mismatch D — Link semantics

Current JEV-RBP treats links as directed in Dijkstra.

The public validator's fallback shortest-path implementation treats physical links as bidirectional.

This must be made an explicit routing-policy choice rather than an accidental implementation detail.

### Current mismatch E — Solution representation

Current internal `BlockingSequence` and `BlockRoute` are typed tuples, which is good internally, but the serializer/parser must preserve the benchmark's arrow-string representation exactly.

### Current mismatch F — Objective

The current objective only contains fixed block + transport.

Full v2.1-compatible work must add handling + interchange and the shared flow calculation.

## 10. Phase 3A conclusion

Phase 3A established the public RAS v2.1 benchmark contract. The repository has
since progressed beyond the original implementation order: the clean-room model,
independent benchmark authority, routing/service separation, benchmark-aligned
objective and canonical VLNS control flow are already implemented.

The remaining reference discrepancies are tracked as explicit research questions.
This document is therefore **benchmark archaeology and contract evidence**, not the
current implementation roadmap.

For current project state, see [PLAN.md](../PLAN.md).

The next benchmark engineering gate is R1-C:

> **Define → check → generate → audit → freeze a controlled small instance.**

The R1-C design is specified in
[docs/r1-controlled-8x50-spec.md](r1-controlled-8x50-spec.md), and the first
engineering gate is the [instance-design checker](r1-controlled-8x50-checker.md).

## Sources

- https://github.com/asu-trans-ai-lab/RAS2026-PSC
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/datasets/schemas/solution_result.schema.json
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/datasets/schemas/demand.schema.json
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/datasets/schemas/node.schema.json
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/datasets/schemas/link.schema.json
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/datasets/schemas/setting.schema.json
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/scoring/fast_validator_v2_0.py
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/scoring/SCORE_README.md
