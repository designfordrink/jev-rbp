# JEV-RBP — Project Plan

## Current checkpoint

**Phase 9 — Controlled real-data experiment v2 implemented.**

Phase 8 established JEV v0 and grouped ranking metrics. Phase 9 now adds the
reproducible runner that compares selectors over the same RBP instances while
keeping the candidate generator, exact evaluator, validator, initial solution,
and exact-evaluation budget fixed.

Current status:
- [x] deterministic linear JEV scorer;
- [x] train/test split by instance;
- [x] Top-K hit-rate and exact-delta regret metrics;
- [x] multi-instance selector experiment runner;
- [x] exact-evaluation budget accounting;
- [x] benchmark-authority final scoring;
- [x] runner unit tests;
- [ ] download/prepare a frozen set of public L1 instances;
- [ ] generate the first real multi-instance JEV dataset;
- [ ] run Identity / Random / RBP Greedy / Linear JEV under K=1, 5, 10;
- [ ] record first scientific results;
- [ ] add runtime and repeated-seed measurements.

## Current research gate

**Reference Reconstruction and R1-C are now parallel tracks.**

The historical Nicolas reconstruction remains the provenance track:
- recover the exact 8×50 source input if it can be established;
- run the archived Greedy / VLNS / MIP;
- perform differential comparison against the clean-room implementation.

At the same time, JEV research is no longer blocked on that historical input. R1-C is
the controlled-benchmark track for building a reproducible small family specifically
designed to expose non-trivial Drop/Add/Swap decision surfaces.

See:
- [docs/reference-reconstruction.md](docs/reference-reconstruction.md)
- [docs/r1-freeze-8x50.md](docs/r1-freeze-8x50.md)
- [docs/r1-controlled-8x50-spec.md](docs/r1-controlled-8x50-spec.md)

Historical reference track:
- [x] reference provenance inventory;
- [x] archived Greedy / VLNS / MIP identified;
- [x] reconstruction protocol documented;
- [x] deterministic freeze tooling;
- [x] non-destructive Kaggle candidate auditor;
- [ ] recover exact historical 8×50 source;
- [ ] reproduce Greedy / VLNS / MIP on the frozen historical input;
- [ ] differential comparison;
- [ ] freeze reference result.

R1-C controlled benchmark track:
- [x] inspect reference solver/data model;
- [x] define controlled 8×50 benchmark specification;
- [ ] implement instance-design checker;
- [ ] implement constrained generator;
- [ ] generate R1-C8x50-A;
- [ ] validate P1–P7 search phenomena;
- [ ] run Greedy / Vanilla VLNS / MIP audit;
- [ ] freeze instance and metadata;
- [ ] resume quantitative JEV comparison.

**Scientific rule:** Nicolas provenance and controlled synthetic benchmark results are
reported as different evidence streams. Neither may be presented as the other.

## Reference Reconstruction

1. **Greedy** — constructive baseline and VLNS warm start.
2. **VLNS** — scalable search baseline.
3. **MIP (Mixed-Integer Programming)** — exact or near-exact teacher on small
   instances.

The MIP result is called an optimum only when optimality is proved; otherwise
the recorded MIP gap is part of the result.

## Research Gate J — JEV after reference

After the reference gate is green, compare Vanilla, Random, Greedy and Linear
JEV under the same candidate generator, exact evaluator, validator, initial
solution and acceptance semantics.

Use K = 1, 2, 5, 10, 20, 50, all where practical. The central measurement is
quality versus exact evaluations / compute, not score alone.

## Scientific rule

At every JEV comparison, keep constant:
- instance;
- initial solution;
- candidate generator;
- exact evaluator;
- validator;
- compute/evaluation budget.

Only the selector should change.

Dataset generation may spend an unlimited exact-evaluation budget because it is
a separate offline labeling stage. Search comparisons must use the declared
per-phase exact-evaluation budget.

An Oracle selector is an **upper bound**, not a valid JEV competitor: it uses
the exact evaluator to rank candidates and therefore violates the information
boundary of the learned selector.

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
- [ ] remaining benchmark/reference discrepancies.

## Phase 3 — Vanilla VLNS reproduction

- [x] physical shortest-path router;
- [x] physical links treated bidirectionally for routing;
- [x] directed block-service graph;
- [x] commodity-type-compatible service routing;
- [x] all-demand rerouting;
- [x] block-volume aggregation;
- [x] unused-block pruning;
- [x] reference Drop/Add/Swap phase ordering;
- [x] exact move evaluation;
- [x] independent benchmark authority;
- [ ] link-capacity-aware physical routing;
- [ ] deterministic small-instance reproduction.

## Phase 4 — Instrumentation

- [x] phase-level search trace;
- [ ] JSONL search trace;
- [ ] state hash;
- [ ] candidate IDs;
- [x] exact evaluation counter;
- [ ] timing;
- [ ] experiment metadata;
- [ ] reproducible run directory.

## Phase 5 — Candidate quality

- [ ] candidate-pool size;
- [ ] legal/illegal ratio;
- [ ] best exact move coverage;
- [ ] Drop/Add/Swap characterization.

## Phase 6 — Selector baselines

- [x] Random;
- [x] Identity;
- [x] hand-designed Greedy selector;
- [x] exact Oracle selector;
- [x] common evaluation-budget harness.

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
- [x] Top-K hit rate;
- [x] regret;
- [ ] ranking correlation.

## Phase 9 — JEV-VLNS

- [ ] Top-1;
- [ ] Top-5;
- [ ] Top-10;
- [x] fixed evaluation-budget runner;
- [ ] runtime comparison;
- [ ] quality comparison;
- [ ] multiple seeds;
- [x] first real multi-case experiment protocol;

## Phase 10 and later

- [ ] MIP teacher on small instances;
- [ ] generalization to larger instances;
- [ ] JEV destroy-selection;
- [ ] LLM-generated neighborhoods;
- [ ] heuristic evolution;
- [ ] JEV-Star.
