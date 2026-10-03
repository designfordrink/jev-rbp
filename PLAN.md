# JEV-RBP — Project Plan

## Current checkpoint

**Phase 8 — JEV v0 experiment harness implemented.**

PR #9 (Phase 7 dataset generation) is merged with successful CI.

Phase 8 now contains:
- [x] deterministic linear delta scorer;
- [x] ridge regularization without a heavyweight ML dependency;
- [x] learned selector interface with no exact-evaluator access;
- [x] initial unit tests;
- [x] JEV v0 protocol documentation.

The first experimental comparison still requires a multi-instance dataset and
a grouped evaluation harness.

## Phase 0 — Repository foundation

- [x] repository;
- [x] PRD;
- [x] development environment;
- [x] CI;
- [x] basic package/tests.

## Phase 1 — Canonical model

- [x] RBP data model;
- [x] GMNS CSV loader;
- [x] commodity/block type model;
- [x] scenario settings;
- [x] typed actions.

## Phase 2 — Reference archaeology

- [x] recover public reference behavior;
- [x] identify Drop/Add/Swap;
- [x] recover phase-ordered control flow;
- [x] recover Dijkstra routing boundary;
- [x] recover objective/acceptance boundary;
- [x] preserve provenance and uncertainty;
- [x] freeze typed interfaces.

Remaining archaeology:
- [ ] exact candidate filters;
- [ ] exact tie-breaking;
- [ ] exact routing caches/optimizations;
- [ ] deterministic reference run;
- [ ] any remaining benchmark/reference discrepancies.

## Phase 3 — Vanilla VLNS reproduction

### 3A — Benchmark archaeology

- [x] identify public RAS v2.1 mirror;
- [x] recover CSV schemas;
- [x] recover solution JSON schema;
- [x] inspect validator C1–C9b;
- [x] freeze objective/stress-score semantics.

### 3B — Search and routing

- [x] physical shortest-path router;
- [x] physical links treated bidirectionally for routing;
- [x] directed block-service graph;
- [x] commodity-type-compatible service routing;
- [x] all-demand rerouting;
- [x] block-volume aggregation;
- [x] unused-block pruning;
- [x] reference Drop/Add/Swap phase ordering;
- [x] regression tests.

### 3C — Exact move evaluation

- [x] generate legal Drop candidates;
- [x] generate legal Add candidates;
- [x] generate legal Swap candidates;
- [x] apply candidate virtually;
- [x] reroute;
- [x] calculate exact objective delta;
- [x] check reference move-level feasibility;
- [x] reproduce acceptance tolerance;
- [ ] reproduce stopping semantics.

### 3D — Benchmark authority

- [x] full independent C1–C9b validator;
- [x] complete fixed + transport + handling + interchange objective;
- [ ] link-capacity-aware physical routing;
- [x] stress score;
- [ ] solution serializer/parser compatibility.

### 3E — Reproduction

- [ ] reproduce a deterministic small reference instance;
- [ ] compare objective components;
- [ ] compare selected moves;
- [ ] document any irreducible differences.

## Phase 4 — Instrumentation

- [ ] JSONL search trace;
- [ ] state hash;
- [ ] candidate IDs;
- [ ] exact evaluation counter;
- [ ] timing;
- [ ] experiment metadata;
- [ ] reproducible run directory.

## Phase 5 — Candidate quality

- [ ] measure candidate-pool size;
- [ ] measure legal/illegal ratio;
- [ ] measure how often best exact move is present;
- [ ] characterize Drop/Add/Swap separately.

## Phase 6 — Selector baselines

- [x] Random;
- [x] Identity;
- [x] hand-designed Greedy selector;
- [ ] exact Oracle selector;
- [ ] common evaluation-budget harness.

## Phase 7 — JEV dataset

- [x] collect vanilla VLNS traces;
- [x] define feature schema;
- [x] split by instance, not by row;
- [ ] freeze dataset version;
- [x] record exact deltas and feasibility labels.

## Phase 8 — JEV v0

- [x] linear scorer;
- [ ] shallow MLP;
- [ ] pairwise ranker;
- [ ] Top-K hit rate;
- [ ] regret;
- [ ] ranking correlation.

## Phase 9 — JEV-VLNS

- [ ] Top-1;
- [ ] Top-5;
- [ ] Top-10;
- [ ] fixed evaluation budget comparison;
- [ ] runtime comparison;
- [ ] quality comparison;
- [ ] multiple seeds.

## Phase 10 and later

- [ ] MIP teacher on small instances;
- [ ] generalization to larger instances;
- [ ] JEV destroy-selection;
- [ ] LLM-generated neighborhoods;
- [ ] heuristic evolution;
- [ ] JEV-Star.

## Scientific rule

At every JEV comparison, keep constant:

- instance;
- initial solution;
- candidate generator;
- exact evaluator;
- validator;
- compute/evaluation budget.

Only the selector should change.

A JEV model that obtains a better objective by simply spending more exact
evaluations is not, by itself, evidence that the selector is better.
