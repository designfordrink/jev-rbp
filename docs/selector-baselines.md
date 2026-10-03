# Selector baselines

## Purpose

Phase 6 introduces a controlled way to compare candidate selectors inside the
recovered Drop → Add → conditional Swap VLNS control flow.

The selector controls which candidates receive expensive exact evaluation.

## Protocol

For each phase:

1. generate the complete deterministic candidate pool;
2. rank that same pool with the selected selector;
3. take the first K candidates;
4. run the same exact evaluator on those candidates;
5. choose the best improving evaluated candidate;
6. validate the resulting state;
7. continue with the recovered phase order.

The selector never decides feasibility and never replaces the exact evaluator.

## Budget

`exact_evaluations_per_phase = K`.

- `K = 1` means one expensive evaluation per phase;
- `K = 5` means five;
- `K = None` means evaluate the complete candidate pool.

`K = None` is the vanilla/full-scan control.

## Baselines

### Identity

`IdentitySelector` preserves deterministic candidate-generator order.
It is a useful non-learning baseline because it introduces no ranking signal.

### Random

`RandomSelector(seed=...)` randomly permutes the same candidate pool.
The seed makes the experiment reproducible.

### Full scan

`exact_evaluations_per_phase=None` evaluates every candidate. This is the
reference best-improvement behavior against which budgeted selectors can be measured.

## Scientific invariant

For a controlled comparison, keep these fixed:

- instance;
- initial state;
- candidate generator;
- exact evaluator;
- validator;
- phase order;
- evaluation budget.

Only the selector and, where applicable, its random seed should change.

## What this enables

This gives the first concrete experiment for the JEV hypothesis:

```text
same candidate pool
      ↓
  selector
      ↓
     Top-K
      ↓
expensive exact evaluation
      ↓
best evaluated move
```

The next layer can replace `IdentitySelector` or `RandomSelector` with a
learned JEV ranker without changing the search/evaluation machinery.