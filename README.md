# JEV-RBP

**JEV-RBP** is a research prototype for testing a specific idea inside the
Railroad Blocking Problem (RBP):

> **VLNS searches for a solution. LLM searches for the algorithm by which
> VLNS will search for a solution. JEV searches for good local actions inside
> that algorithm.**

JEV-RBP is deliberately the **small experimental lower layer** of the broader
JEV-Star research program. It is not intended to replace VLNS, the exact
evaluator, or the validator.

## What is being tested?

The Railroad Blocking Problem asks us to design directional rail blocks,
route commodities through a block-service network, and choose physical routes
subject to infrastructure and operating constraints.

The baseline used by this project is a Very Large Neighborhood Search (VLNS):
a metaheuristic that repeatedly changes the current solution through large
neighborhood moves such as:

- **Drop** — close an existing block;
- **Add** — open a candidate block;
- **Swap** — close one block and open another.

The recovered public reference implementation uses the following control flow:

\`\`\`
current solution
      |
      +--> best Drop ----> apply if improving
      |
      +--> best Add  ----> apply if improving
      |
      +--> if neither improved:
             best Swap --> apply if improving
      |
      +--> otherwise stop
\`\`\`

The important detail is that this is **phase ordered**, not one global scan over
Drop + Add + Swap. A successful Drop is applied before Add candidates are
evaluated.

JEV is introduced only after this baseline is stable:

\`\`\`
candidate actions
      |
      v
   JEV rank
      |
      v
    Top-K
      |
      v
exact rerouting + objective
      |
      v
   validator
      |
      v
 accept / reject
\`\`\`

Therefore JEV is a **selector**, not a source of truth.

## Current implementation status

**Phase 9 — controlled real-data experiment v2**

Implemented:

- clean-room RBP model and public-data loader;
- bidirectional physical shortest-path routing;
- directed block-service routing;
- benchmark-authoritative Drop/Add/Swap evaluation;
- full benchmark feasibility checks at search acceptance/final scoring;
- canonical shared VLNS control flow;
- Random, Identity, RBP Greedy and Linear JEV selectors;
- deterministic JEV dataset collection;
- multi-case train/test split by case;
- fixed exact-evaluation budgets K=1/5/10;
- controlled real RAS L1 experiment v2;
- optional Vanilla VLNS full-candidate baseline.

The current experiment cases are demand subsets of one L1 physical network, so
they are **not independent benchmark instances**. They are suitable for testing
selector behavior across demand patterns, but not for claiming cross-network
generalization or an official competition score.

Next:

- execute and analyze the v2 real-data run;
- measure runtime and repeated seeds;
- build genuinely independent small instances for stronger generalization tests;
- then redesign JEV ranking features/model (JEV v1).

The project intentionally separates **archaeology** from **implementation**:
the recovered competition/reference code remains under \`data/reference/archive/\`
as provenance material; the solver itself is a clean-room implementation of
the documented behavior.

## Architecture

\`\`\`
                     future
                       LLM
                        |
                invent / modify
                 search heuristics
                        |
                        v
              +-------------------+
              |       VLNS        |
              | solution search   |
              +---------+---------+
                        |
                 candidate actions
                        |
                        v
                 +------+------+
                 |     JEV     |
                 | local ranker|
                 +------+------+
                        |
                     Top-K
                        |
                        v
              exact evaluator
              + rerouting
                        |
                        v
                   Validator
                        |
                        v
                    Benchmark
\`\`\`

The critical experimental invariant is:

> Removing JEV must leave the candidate generator, exact evaluator, validator
> and acceptance semantics unchanged.

This makes it possible to attribute any change in search efficiency to the
selector rather than to a hidden change in the optimization problem.

## Two graphs, not one

A central implementation detail is the separation between the **physical
network** and the **blocking-service network**.

### Physical network

The physical network contains GMNS track links and is used for shortest-path
routing of a block.

The recovered reference data loader treats physical links as traversable in
both directions for shortest-path computation, while retaining the original
link identifier.

### Blocking-service network

A block is a **directed** service arc:

\`\`\`
Yard A  ----block---->  Yard B
\`\`\`

A block A → B and a block B → A are different services and have separate
fixed costs.

Commodity routing happens on this directed block graph. Each service arc is
backed by a physical route through the rail network.

This separation is essential:

\`\`\`
physical graph                 service graph

track links                    opened blocks
     |                              |
     v                              v
Dijkstra shortest path        commodity routing
     |                              |
     +----------> block <-----------+
\`\`\`

See [docs/service-routing.md](docs/service-routing.md).

## Repository map

\`\`\`
jev-rbp/
├── README.md
├── README_RU.md
├── PRD.md
├── PLAN.md
├── data/
│   └── reference/
│       └── archive/          # recovered reference implementation
├── docs/
│   ├── architecture.md
│   ├── benchmark-archaeology.md
│   ├── experiments.md
│   ├── reference-vlns.md
│   ├── rbp.md
│   ├── research.md
│   ├── service-routing.md
│   └── solver-archaeology.md
├── src/jev_rbp/
│   ├── actions.py
│   ├── core.py
│   ├── evaluation.py
│   ├── greedy.py
│   ├── io.py
│   ├── objective.py
│   ├── problem.py
│   ├── rerouting.py
│   ├── routing.py
│   ├── selectors.py
│   ├── service.py
│   ├── validator.py
│   └── vlns.py
└── tests/
\`\`\`

## Development

Requires Python 3.11+.

\`\`\`bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
jev-rbp
\`\`\`

## Research ladder

1. Reproduce the reference VLNS control flow.
2. Reproduce candidate generation and exact move evaluation.
3. Reproduce the benchmark validator and objective.
4. Instrument the search and collect traces.
5. Measure candidate-pool quality.
6. Train a small JEV ranker.
7. Compare Random / Greedy / Vanilla VLNS / JEV Top-K.
8. Test generalization.
9. Use MIP as an exact teacher on small instances.
10. Let an LLM propose new neighborhoods and search heuristics.
11. Evolve toward JEV-Star.

## Research documents

- [PRD](PRD.md) — research requirements and hypotheses.
- [PLAN](PLAN.md) — implementation roadmap and current checkpoints.
- [Architecture](docs/architecture.md) — module and responsibility boundaries.
- [Service routing](docs/service-routing.md) — physical graph vs directed block graph.
- [Solver archaeology](docs/solver-archaeology.md) — recovered reference behavior.
- [Benchmark archaeology](docs/benchmark-archaeology.md) — RAS v2.1 contract.
- [Experiments](docs/experiments.md) — controlled experiment protocol.
- [RBP model](docs/rbp.md) — canonical problem definition.

## References

- [RAS2026-PSC public mirror](https://github.com/asu-trans-ai-lab/RAS2026-PSC)
- [Nicolas Bridelance — Railroad Blocking VLNS Metaheuristic](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-vlns-metaheuristic)
- [Nicolas Bridelance — Railroad Blocking MIP Pyomo HiGHS](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-mip-pyomo-highs)
- [AnniceNajafi/rasblocking](https://github.com/AnniceNajafi/rasblocking)

## Research status

This repository is an experimental research codebase. The goal of v0.1 is not
to prove that JEV is better than VLNS. A negative result is useful if the
comparison is controlled and reproducible.

The broader JEV-Star architecture is documented separately from this
RBP-specific implementation.
