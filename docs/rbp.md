# RBP Canonical Model

This document freezes the clean-room problem model used by JEV-RBP.

## 1. Input model

The RAS benchmark uses GMNS-style CSV files:

- \`node.csv\` — physical nodes and yards;
- \`link.csv\` — physical track segments;
- \`demand.csv\` — yard-to-yard commodity demands;
- \`setting.csv\` — global parameters.

The five commodity types are:

- Merchandise;
- Intermodal;
- Coal;
- Grain;
- Automobile.

Intermodal and Automobile are direct-only in the benchmark specification.

## 2. Two notions of direction

There are two different meanings of direction.

### Physical links

The CSV link record contains \`from_node_id\` and \`to_node_id\`. For the
reference shortest-path computation, the recovered loader constructs an
undirected physical graph, so a physical link can be traversed in either
direction while retaining its original link ID.

### Blocks

A block is a directional service:

\`\`\`
A -> B
\`\`\`

A → B and B → A are separate blocks and therefore separate fixed-cost
decisions.

The service graph is directed even though the physical shortest-path graph is
treated as bidirectional.

## 3. Solution state

A complete blocking solution contains:

\`\`\`
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
    physical path through the network
\`\`\`

## 4. Objective

The benchmark operating cost consists of:

1. block fixed cost;
2. transportation cost;
3. classification handling cost;
4. interchange cost.

For a JEV experiment, the authoritative move delta is:

\`\`\`
exact objective(after action) - objective(before action)
\`\`\`

A selector must never replace this calculation with a learned estimate.

Stress scenarios additionally use the benchmark Stress Score with an
unserved-demand penalty.

## 5. Constraints

The benchmark contract covers:

- C1 — flow conservation / valid blocking sequences;
- C2 — classification track limit;
- C3 — yard handling capacity;
- C4 — minimum block volume;
- C5 — physical link throughput capacity;
- C6 — maximum circuitous ratio;
- C7 — single-path uniqueness;
- C8 — one commodity type per block;
- C9b — demand-volume consistency in the released validator.

The exact authoritative definitions are recorded in
[benchmark-archaeology.md](benchmark-archaeology.md). The current clean-room
validator is intentionally not yet a full implementation of all constraints.

## 6. Default parameters

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

## 7. Rerouting boundary

Given an open block design:

\`\`\`
open blocks
    |
    v
directed service graph
    |
    v
commodity routing
    |
    +--> block sequences
    |
    +--> block volumes
    |
    v
physical route for each used block
\`\`\`

The service router uses the physical shortest route of each block as its
transport component and adds intermediate-yard handling cost.

## 8. JEV boundary

\`\`\`
candidate actions
       |
       v
      JEV
       |
       v
    Top-K
       |
       v
 exact rerouting
       |
       v
 objective + validator
\`\`\`

The experiment is meaningful only if the last two stages remain independent of
JEV.
