# JEV-RBP — Project Plan

## Current status

**Phase 3 — Vanilla VLNS reproduction (seed baseline)**

Phase 3A archaeology is complete: the RAS v2.1 public mirror, schemas, validator, scoring package, and solution contract have been frozen in `docs/benchmark-archaeology.md`.

Completed:
- Phase 0 repository foundation.
- Phase 1 canonical RBP model/specification.
- Phase 2 behavioral archaeology of the public reference VLNS.
- Typed Drop/Add/Swap action boundary.
- Routing and exact-evaluation boundaries.
- Best-improving VLNS orchestration shell.
- Deterministic selector baselines.
- Tests for the new boundaries.

The reference notebook is a Kaggle artifact. Its documented behavior is sufficient to freeze the algorithmic control flow, but exact internal function names, data structures, filters and tie-breaking are not yet claimed as reproduced.

## Phase 2 — Baseline archaeology

### Done

- [x] recover public reference behavior;
- [x] identify Drop/Add/Swap;
- [x] identify best-improving control flow;
- [x] identify Dijkstra-based routing boundary;
- [x] identify objective/acceptance boundary;
- [x] map reference behavior to JEV-RBP modules;
- [x] record provenance and uncertainty;
- [x] freeze typed search-loop interfaces.

### Remaining

- [x] recover exact notebook source/runtime where possible;
- [ ] identify exact candidate-generation filters;
- [ ] identify exact tie-breaking;
- [ ] identify routing caches/implementation optimizations;
- [ ] identify exact stopping semantics;
- [ ] reproduce one small reference run.

## Phase 3 — Vanilla VLNS reproduction

### Tasks

- [x] dataset loader;
- [x] minimal greedy seed;
- [ ] Drop;
- [ ] Add;
- [ ] Swap;
- [x] exact physical shortest-path routing;
- [x] initial objective components (fixed block + transport);
- [x] independent structural validator for the seed;
- [ ] stopping criteria;
- [ ] benchmark runner.

### Phase 3 checkpoint

The repository now has an executable seed path: GMNS CSVs → typed RBP instance → Dijkstra shortest path → direct-block greedy solution → structural validation → objective calculation.

This is deliberately **not yet a full reference VLNS reproduction**. Drop/Add/Swap over the blocking-service graph and the full benchmark objective/constraint set remain next.

### Exit criteria

A small public instance can be solved end-to-end and the result can be independently validated.

## Phase 4 — Validator

- [ ] implement C1–C9b;
- [ ] negative tests;
- [ ] property tests;
- [ ] edge cases.

## Phase 5 — Instrumentation

- [ ] JSONL trace writer;
- [ ] state hashing;
- [ ] candidate IDs;
- [ ] timing;
- [ ] exact evaluation counter;
- [ ] experiment metadata.

## Phase 6 — Candidate Generator

- [ ] Drop/Add/Swap candidate generation;
- [ ] cheap feasibility filters;
- [ ] deterministic ordering;
- [ ] candidate-pool statistics.

## Phase 7 — Selector baselines

- [ ] Random;
- [ ] Greedy;
- [ ] Oracle best;
- [ ] JEV placeholder.

## Phase 8 — JEV dataset

- [ ] trace exporter;
- [ ] instance-level train/validation/test split;
- [ ] feature schema/versioning;
- [ ] frozen dataset.

## Phase 9 — JEV v0

- [ ] linear scorer;
- [ ] shallow MLP;
- [ ] pairwise ranker;
- [ ] Top-K/regret metrics.

## Phase 10 — JEV-VLNS

- [ ] Top-1/5/10;
- [ ] same candidate generator;
- [ ] same evaluator;
- [ ] same validator;
- [ ] same budget.

## Later

Phase 11 generalization → Phase 12 MIP oracle → Phase 13 destroy selector → Phase 14 LLM-generated neighborhoods → Phase 15 heuristic evolution → Phase 16 JEV-Star.
