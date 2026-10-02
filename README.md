# JEV-RBP

**JEV-RBP** is a research prototype for combining a compact JEV-like System-1 selector with Very Large Neighborhood Search (VLNS) for the Railroad Blocking Problem (RBP).

> **VLNS ищет решение. LLM ищет алгоритм, которым VLNS будет искать решение. JEV ищет хорошие локальные действия внутри этого алгоритма.**

## Project status

Early research / experimental.

The first milestone is deliberately narrow: test whether a small learned selector can improve or accelerate local action selection inside an existing VLNS search loop.

This repository is **not** intended to replace VLNS, MIP, or the RBP validator with an LLM.

## Architecture

```
                 LLM
                  │
          future: invent heuristics
                  │
                  ▼
                 VLNS
                  │
          candidate generation
                  │
                  ▼
                 JEV
                  │
            local action
                  │
                  ▼
              Validator
                  │
                  ▼
              Benchmark
                  │
                  ▼
                Score
```

## Research ladder

1. Reproduce vanilla VLNS
2. Instrument the search
3. Study candidate generation
4. Train JEV on search traces
5. Compare Random / Greedy / JEV
6. Integrate JEV into VLNS
7. Use MIP as an oracle on small instances
8. Test generalization
9. Let LLM generate new search heuristics
10. Evolve toward JEV-Star

See [PRD.md](PRD.md) and [PLAN.md](PLAN.md).

## Core principle

JEV is a **selector**, not the source of truth.

Candidate legality is determined by the problem/search layer. Exact evaluation determines the actual effect of an action. The validator independently determines feasibility.

This separation makes the experiments measurable and scientifically reproducible.

## References

- RBP competition / specification: use the authoritative competition materials for the exact benchmark and validator semantics.
- Nicolas Bridelance's public RBP experiments:
  - [Railroad Blocking MIP Pyomo HiGHS](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-mip-pyomo-highs)
  - [Railroad Blocking VLNS Metaheuristic](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-vlns-metaheuristic)

## License

To be defined.
