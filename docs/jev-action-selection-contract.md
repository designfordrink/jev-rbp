# JEV action-selection contract

## What JEV receives today

The current prototype uses Linear JEV, not an LLM prompt.

JEV is a small learned selector: it receives cheap features for every candidate action and ranks the actions. It does not receive the exact evaluator, benchmark validator, or future objective value.

```
state + candidate action
        |
        v
cheap feature extractor
        |
        v
JEV
        |
        v
ranked candidate list
        |
        v
exact evaluator checks only the top K
```

The exact evaluator remains the authority. JEV only decides which local actions deserve expensive evaluation.

## The important discovery

The first feature set was too poor for local decision making.

For a Drop action it contained phase, candidate index, open-block count, demand count, block volume, physical distance and outgoing degree.

It did NOT say whether the block was actually used by a demand.

Therefore two blocks with the same geometry could look identical even when one is carrying demand and the other is unused.

The current extractor adds:

- drop_used_by_demand_count
- drop_used_volume
- drop_unused
- drop_is_direct_demand_block
- add_direct_demand_count
- add_direct_demand_volume

These remain cheap features: they inspect the current state and demand table without running the exact evaluator.

## What choices does JEV see?

### DROP

For example:

```
DROP block 101
DROP block 102
DROP block 103
...
```

JEV should receive enough context to distinguish:

- block identity;
- from/to yards;
- commodity type;
- block volume;
- physical distance;
- number of demands using it;
- volume carried through it;
- whether it is unused;
- outgoing-block pressure;
- direct demand count/volume for this OD pair.

### ADD

For example:

```
ADD 10 -> 28, MANIFEST
ADD 10 -> 31, MANIFEST
ADD 12 -> 28, MANIFEST
...
```

JEV should know physical distance, commodity, current outgoing degree, and direct demand count/volume.

### SWAP

A swap combines two choices:

```
what I remove
      +
what I add
      =
whether this structural change is promising
```

Therefore the selector needs the context of both the dropped block and the added block.

## Proposed LLM-JEV prompt

This is NOT yet used by the repository. It is the proposed interface for a later LLM/JEV experiment.

```
You are JEV, a local-action selector inside a VLNS search.

Goal:
Choose the most promising candidate actions for exact evaluation.
You are NOT the final validator.
Do not assume an action is feasible merely because it looks attractive.

Current phase: DROP
Objective: minimize operating cost.

Current state:
- open blocks: 12
- demands: 8
- current objective: 7261129
- yard 10 outgoing blocks: 2 / 3 tracks

Candidate actions:

A1:
  action: DROP
  block_id: 1001
  from: 10
  to: 28
  commodity: MANIFEST
  volume: 850
  distance: 420
  used_by_demands: 1
  used_volume: 850
  unused: false

A2:
  action: DROP
  block_id: 1002
  from: 10
  to: 28
  commodity: MANIFEST
  volume: 850
  distance: 420
  used_by_demands: 0
  used_volume: 0
  unused: true

A3:
  action: DROP
  block_id: 1003
  from: 12
  to: 31
  commodity: MANIFEST
  volume: 600
  distance: 310
  used_by_demands: 1
  used_volume: 600
  unused: false

Return candidate IDs in descending order of expected improvement.
Return only JSON.
```

Expected output:

```json
{"ranking":["A2","A3","A1"]}
```

The exact evaluator then decides whether A2 really improves the solution.

## What JEV must NOT receive

To preserve the architecture, the selector should not receive:

- exact objective delta;
- exact feasibility result;
- benchmark validator result;
- another exact evaluator's answer;
- future search results.

Otherwise JEV becomes an evaluator rather than a search-policy component.

## Three levels of JEV input

### JEV-0: impoverished

```
phase + distance + volume + degree
```

This is the original baseline.

### JEV-1: state-aware

JEV-0 plus:

- used_by_demands;
- used_volume;
- direct_demand_volume;
- direct_demand_count.

This is the next experiment.

### JEV-2: relational

Add compact information about structural consequences:

- number/volume of demands that could use the block;
- current alternative blocks;
- route length versus direct physical distance;
- track pressure;
- potential consolidation volume;
- whether the candidate is currently essential for a demand;
- whether an added block creates a shorter service path.

JEV-2 is much closer to the intended "good local action" concept.

## Experimental rule

Every JEV experiment should record:

```
state
candidate menu
features shown to JEV
JEV ranking
exact evaluations of selected candidates
oracle ranking
```

Otherwise a failed experiment is ambiguous: JEV may have made a bad choice, or it may simply not have been given the information required to make the choice.
