# JEV-RBP Architecture

## Current boundary

Phase 2 freezes the control-flow boundary before the real solver is implemented.

```text
RBP instance
    |
    v
Search state
    |
    v
Candidate generator
    +--------------------+
    |                    |
    v                    v
Selector              Exact evaluator
    |                    |
    v                    |
ranked candidates        |
    |                    |
    +--------> Top-K ----+
                         |
                         v
                     Validator
                         |
                         v
                       Apply
                         |
                         v
                    next state
```

For the vanilla baseline, all generated candidates are exactly evaluated and the best improving move is applied.

For JEV-VLNS, the intended change is the selector/ranking stage only. The exact evaluator, validator, candidate generator and acceptance semantics remain controlled.

## Module boundaries

| Module | Responsibility |
|---|---|
| src/jev_rbp/problem.py | canonical RBP data model |
| src/jev_rbp/actions.py | typed Drop/Add/Swap actions |
| src/jev_rbp/routing.py | physical-network routing boundary |
| src/jev_rbp/evaluation.py | authoritative move evaluation boundary |
| src/jev_rbp/vlns.py | best-improving search orchestration |
| src/jev_rbp/selectors.py | Random/identity baselines and future JEV |
| future validator.py | independent feasibility authority |

## Critical invariant

JEV is never allowed to silently become a validator or objective estimator.

```text
generate legal candidates
        ↓
rank cheaply
        ↓
evaluate selected candidates exactly
        ↓
validate
        ↓
accept
```

If JEV is removed, the same candidate generator and exact evaluator must still produce the vanilla baseline.

## Reference mapping

See reference-vlns.md for the archaeology of the public Bridelance VLNS notebook and the distinction between verified behavior and implementation details that still need recovery.
