# JEV v0

JEV (Just Enough Value) v0 is the first learned local-action selector in this
repository.

It predicts the **exact objective delta** of a candidate action from cheap
features. A lower predicted delta is ranked first because the RBP objective is
minimized.

## Architecture

```
candidate generator
       |
       v
 cheap features -----> JEV v0 (linear scorer)
       |                         |
       |                         v
       |                    ranked actions
       |                         |
       +-------------------------+
                                 v
                         exact evaluator
                                 |
                                 v
                             validator
```

The selector has no access to the exact evaluator, benchmark validator, or
future objective value. Those components remain the authority.

## Why linear first?

The first model is deliberately small and dependency-free:

- standardized numeric features;
- ridge-regularized linear regression;
- deterministic Gaussian elimination;
- no PyTorch/scikit-learn dependency.

This isolates the first scientific question: can a cheap learned score improve
which candidates receive a fixed exact-evaluation budget?

## Training target

For feasible candidates:

```
target = objective_after - objective_before
```

Negative values are improvements. Infeasible candidates currently use zero as
the regression target; feasibility remains an independent label and must not be
confused with objective prediction.

## Experimental protocol

Keep these fixed:

- problem instance;
- initial solution;
- candidate generator;
- exact evaluator;
- validator;
- exact-evaluation budget.

Only the selector changes.

The required baseline set is:

- Identity;
- seeded Random;
- hand-designed RBP Greedy;
- Linear JEV.

The next implementation step is a grouped experiment harness that measures
Top-K hit rate, regret, and final objective under the same evaluation budget.

Dataset train/test splitting must be done by instance, not by candidate row.
The current Phase 7 row format does not yet carry an instance identifier, so
this is an explicit remaining integration task.
