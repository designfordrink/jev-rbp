# Multi-instance JEV experiment runner

## Purpose

`experiment_runner.py` runs selector comparisons under a common **exact-evaluation budget**.

An exact evaluation means running the authoritative move evaluator for one candidate. This is the expensive operation that JEV is intended to reduce.

For every experiment case the following are fixed:

- RBP instance;
- initial solution;
- candidate generator;
- exact evaluator;
- move applier;
- validator;
- maximum number of iterations;
- exact evaluations allowed per phase.

Only the selector changes.

## Result fields

Each run records:

- selector name;
- instance ID;
- exact-evaluation budget;
- actual exact evaluations;
- accepted moves;
- iterations;
- final benchmark operating cost;
- final Stress Score;
- benchmark feasibility.

The final benchmark calculation is deliberately performed after search and is not counted as a move evaluation. It is the independent measurement authority, not part of the selector's search budget.

## Recommended first experiment

Use several public RAS 2026 L1 instances as independent cases.

Create a training dataset with `collect_jev_dataset()` using the same initial solution and candidate generator that will be used for evaluation. Split by **instance**, never by individual candidate rows.

Then:

1. fit `LinearJEVModel` only on training-instance rows;
2. construct a `LinearJEVSelector`;
3. evaluate on unseen instances;
4. compare Identity, Random, RBP Greedy, and Linear JEV;
5. repeat with exact-evaluation budgets K=1, K=5, K=10;
6. keep Oracle separately as an upper-bound reference.

A result is scientifically useful only if the same instances, initial states, candidate pools, exact evaluator, validator and evaluation budgets are used for every selector.

## Public data

The public RAS2026-PSC repository publishes L1/L2/L3 datasets. Some large network files are distributed as ZIP archives, so the JEV-RBP repository does not vendor those benchmark datasets. Keep local experiment data outside the source tree or in a separately versioned data artifact.

The current clean-room loader expects an extracted directory containing:

- `node.csv`
- `link.csv`
- `demand.csv`
- `setting.csv`

The first real experiment should record the public dataset release/version and hashes of the local files in its experiment metadata.
