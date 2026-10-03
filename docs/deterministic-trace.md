# Phase 3E — Deterministic VLNS Reproduction

Phase 3E freezes the reference VLNS control flow into an observable experiment trace.

## Trace contract

Each evaluated phase records:
- iteration;
- phase (`drop`, `add`, `swap`);
- candidate count;
- evaluated count;
- whether an improving move was accepted;
- exact objective delta.

The trace is intentionally independent of JEV. It records what the search engine did, not why a selector preferred an action.

## Reference semantics

For each iteration:
1. evaluate all Drop candidates and accept the best strict improvement;
2. on the resulting state, evaluate all Add candidates and accept the best strict improvement;
3. only when neither Drop nor Add improved, evaluate Swap candidates;
4. stop when none of the three phases produces an improvement.

The strict improvement tolerance is `1e-6`.

## Experimental invariant

When comparing selectors later, keep fixed:
- problem instance;
- initial solution;
- candidate universe;
- exact evaluator;
- validator;
- compute/evaluation budget.

Only candidate selection may change.

This makes the comparison suitable for the JEV hypothesis: whether a learned local-action selector can reduce evaluation work while preserving solution quality.