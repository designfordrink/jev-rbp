# JEV-RBP

**JEV-RBP** is a research prototype for combining a compact JEV-like System-1 selector with Very Large Neighborhood Search (VLNS) for the Railroad Blocking Problem (RBP).

> **VLNS ищет решение. LLM ищет алгоритм, которым VLNS будет искать решение. JEV ищет хорошие локальные действия внутри этого алгоритма.**

## Status

**Phase 0 — repository foundation.**

The repository now contains the research specification, experiment protocol, Python package scaffold, typed core interfaces, tests, and CI. The actual RBP/VLNS implementation is intentionally not yet connected.

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
          exact evaluator
                  │
                  ▼
              Validator
                  │
                  ▼
              Benchmark
```

JEV is a **selector, not the source of truth**. Candidate legality belongs to the search/problem layer, exact evaluation determines the actual effect, and the validator independently determines feasibility.

## Local development

Requires Python 3.11+.

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
jev-rbp
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

See [PRD.md](PRD.md), [PLAN.md](PLAN.md), [docs/architecture.md](docs/architecture.md), and [docs/experiments.md](docs/experiments.md).

## References

- [Nicolas Bridelance — Railroad Blocking VLNS Metaheuristic](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-vlns-metaheuristic)
- [Nicolas Bridelance — Railroad Blocking MIP Pyomo HiGHS](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-mip-pyomo-highs)
- [Public validator/diagnostics implementation](https://github.com/AnniceNajafi/rasblocking)

## License

To be defined.
