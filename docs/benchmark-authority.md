# Benchmark authority

## Purpose

`BenchmarkAuthority` is an independent authority for the RAS 2026 Railroad Blocking Problem (RBP). It is deliberately separated from candidate generation, VLNS, and JEV.

The solver may propose a solution. The benchmark authority decides whether the solution satisfies the benchmark constraints and computes benchmark cost and Stress Score.

The released public v2.1 validator defines checks for flow conservation, no-subtour blocking sequences, yard track limits, handling capacity, minimum block volume, physical-link capacity, maximum circuitous ratio, single-path uniqueness, commodity-type separation, direct-only Intermodal/Automobile routing, and demand-volume consistency.

## Checks

### C1 — Flow and physical-route consistency

- every demand has a non-empty blocking sequence;
- first block starts at the demand origin;
- last block ends at the demand destination;
- consecutive blocks are connected;
- referenced blocks exist;
- declared physical routes connect their block endpoints;
- physical route link IDs correspond to the traversed node pairs;
- physical route node IDs contain no repeated node.

The physical network is treated as bidirectional.

### C1b — No subtour

A blocking sequence may not revisit a yard.

### C2 — Classification-yard track limit

The v2.1 benchmark classification rule counts Manifest/Bulk blocks in this clean-room model; Coal and Grain are represented as the canonical Bulk block type. Intermodal and Automobile blocks are not counted by this check.

### C3 — Yard handling capacity

For each intermediate yard, the authority sums the volume classified there and compares it with handling_capacity.

### C4 — Minimum block volume

The minimum volume depends on the shortest physical distance between block endpoints: <100 mi, 100–500 mi, or >500 mi.

### C5 — Physical-link capacity

For every physical link, the authority sums volumes of all block routes using that link and checks the result against link capacity. A physical link is capacity-shared by both traversal directions.

### C6 — Maximum circuitous ratio

The submitted physical route must not exceed shortest_path × max_circuitous_ratio.

### C7 — Single-path uniqueness

A demand must not be represented by multiple distinct blocking paths.

### C8 — Commodity-type separation

A block may not be shared by different commodity types.

### C9 — Direct-only rule

Intermodal and Automobile demands must use exactly one block, and that block must be their direct origin-destination block.

### C9b — Demand-volume consistency

A submitted sequence must have positive volume and may not transport more than the corresponding demand. Under-service is intentionally allowed; its residual volume is penalized by Stress Score instead of being treated as a feasibility violation.

## Objective

Operating cost = fixed + transport + handling + interchange.

Transport uses the physical route actually assigned to each block. Handling is charged at intermediate classification yards.

Interchange follows the public v2.1 two-endpoint Class-I rule: compare the railroad of the block origin and destination yards; charge one interchange when both are recognized Class-I railroads and differ; normalize CSXT to CSX; intermediate physical-path nodes do not create additional interchange charges.

## Stress Score

For each demand, served volume is the positive submitted blocking volume, capped at demand volume. Unserved volume contributes unserved volume × shortest physical distance.

Stress Score = operating cost + M × unserved car-miles.

## Scientific boundary

`BenchmarkAuthority` is not used to generate moves and does not know whether a move came from Vanilla VLNS, Random selection, JEV, or another solver.

```text
Candidate Generator
        ↓
Selector (future JEV)
        ↓
Exact Move Evaluator
        ↓
Solution
        ↓
BenchmarkAuthority  ← independent authority
        ↓
cost / feasibility / Stress Score
```

The public benchmark package and its v2.1 validator are the external reference for this layer:
https://github.com/asu-trans-ai-lab/RAS2026-PSC