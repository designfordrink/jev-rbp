# RBP Canonical Model

This document freezes the problem model used by JEV-RBP v0.1. It follows the released RAS 2026 v2.1 benchmark package and validator.

## 1. Input model

The benchmark uses GMNS-style CSV inputs:

- node.csv — physical nodes and yards
- link.csv — physical track segments
- demand.csv — yard-to-yard commodity demands
- setting.csv — global parameters

The solver must record the exact dataset version and scenario multiplier in every run.

### Node

Important fields: node_id, node_type, name, yard_type, yard_level, railroad_id, num_tracks, handling_capacity, handling_cost, is_interchange.

Only node_type=yard nodes are demand endpoints and classification points.

### Link

Important fields: link_id, from_node_id, to_node_id, length, capacity, railroad_id.

Links are directed. A bidirectional physical connection is represented by two directed rows.

### Demand

A demand contains commodity_id, commodity_type/block_type, origin_yard_id, dest_yard_id and volume.

The five benchmark commodity types are Merchandise, Intermodal, Coal, Grain and Automobile.

Intermodal and Automobile are direct-only: their blocking sequence must contain one direct block.

## 2. Solution state

A blocking solution contains three coupled components:

~~~text
Block Design
    block_id
    from_yard
    to_yard
    commodity_type
    block_volume

Blocking Sequence
    commodity
    block_1 -> block_2 -> ...

Block Route
    block
    physical path through network
~~~

## 3. Objective

The operating objective consists of fixed block cost + transportation cost + handling cost + interchange cost.

The released validator also computes a Stress Score by adding a penalty for unserved car-miles.

For JEV experiments, objective_after - objective_before is the authoritative move delta. A selector must never estimate this as truth.

## 4. Current validation contract

The released v2.0 validator implements:

1. Flow conservation.
2. Classification track limit.
3. Yard handling capacity.
4. Minimum block volume.
5. Link capacity.
6. Maximum circuitous ratio.
7. Single-path uniqueness.
8. Single commodity type per block.
9. Direct-block rule for Intermodal and Automobile.
9b. Demand-volume consistency.

The v2.0 validator also rejects subtours/repeated yards in a blocking sequence and applies a defined interchange-cost rule.

## 5. Parameters

| Parameter | Default |
|---|---:|
| min block volume <100 mi | 350 |
| min block volume 100–500 mi | 700 |
| min block volume >500 mi | 1050 |
| max circuitous ratio | 1.3 |
| operating cycle | 70 days |
| block fixed cost | 2500 |
| transport cost coefficient | 1 |
| interchange cost | 100 |
| stress penalty M | 5 |
| demand multiplier | 1.0 |

The demand multiplier is part of the scenario definition and must be recorded explicitly.

## 6. Shortest paths

Shortest-path distance is used by minimum-block-volume checks, circuitous-ratio checks and stress-score unserved car-mile calculation.

The released validator prefers the supplied OD distance matrix and falls back to sparse Dijkstra on the physical network for missing pairs. JEV-RBP should expose this as one shared shortest-path service.

## 7. Implication for JEV

~~~text
RBP instance
    ↓
current SolutionState
    ↓
legal CandidateAction
    ↓
JEV ranking
    ↓
exact move evaluation
    ↓
validator
    ↓
accept/reject
    ↓
new SolutionState
~~~

This defines the experimental boundary:

- candidate generator: what may be tried
- JEV: what should be tried first
- exact evaluator: what actually happens
- validator: whether the resulting solution is legal

No learned component replaces the last two in v0.1.

## Sources

- https://github.com/asu-trans-ai-lab/RAS2026-PSC
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/datasets/DATASET_README.md
- https://github.com/asu-trans-ai-lab/RAS2026-PSC/blob/main/scoring/fast_validator_v2_0.py
