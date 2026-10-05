# Controlled RAS L1 experiment v2

This is the second real-data experiment for JEV-RBP. It fixes the main
methodological weaknesses of the first L1 prototype:

- no deliberately redundant duplicate blocks;
- several demand-pattern cases instead of one train/test slice;
- training labels collected from several cases;
- test ranking measured over several candidate pools;
- the same canonical VLNS engine for every selector;
- optional Vanilla VLNS as a true full-candidate baseline;
- identical benchmark authority and acceptance semantics for all selectors.

## What this experiment is — and is not

The cases are demand subsets of the same public RAS2026-PSC v2.1 L1 physical
network. They are therefore **not independent benchmark instances**.

The experiment can test whether a JEV model transfers across different demand
patterns on the same infrastructure. It cannot establish generalization to a
new physical network.

Prepare the public L1 files with:

    python scripts/download_ras_l1.py

The download script verifies the published L1 link archive SHA-256.

## Protocol

Default configuration:

- 20 selected demands;
- 5 cases × 4 demands;
- first 3 cases for JEV training;
- remaining 2 cases for test;
- 2 offline dataset iterations per case;
- 2 search iterations;
- exact-evaluation budgets K=1, 5, 10 per phase;
- Identity, Random, RBP Greedy and Linear JEV;
- optional Vanilla VLNS with the --include-vanilla flag.

Each case has its own direct-block feasible initial solution. Every selector in
a case starts from exactly that same state and uses exactly the same:

1. candidate generator;
2. exact move evaluator;
3. benchmark validator;
4. acceptance rule;
5. search iteration limit.

Only candidate ranking changes.

### Vanilla VLNS

Vanilla VLNS is the canonical search without a selector: selector=None.

It evaluates the complete candidate pool in each phase. Consequently its exact
evaluation count is not comparable to K=1/5/10 selector runs; it is an
important quality baseline, but not a fixed-budget competitor.

Use:

    python scripts/run_l1_experiment.py --include-vanilla

when the full baseline is affordable.

## Outputs

The run writes:

- train.jsonl — exact offline labels from training cases;
- test.jsonl — exact labels used for ranking diagnostics;
- model.json — fitted Linear JEV model;
- ranking.json — Top-K hit rate and regret on test pools;
- config.json — exact case/demand split and protocol;
- results.csv / results.json — final search results.

## Metrics

### Selector ranking

For every (case, iteration, phase) pool:

- **Top-K hit rate** asks whether an optimal exact action appears among JEV's
  first K candidates;
- **regret** is the exact objective delta of the first feasible ranked action
  minus the best feasible delta in that pool.

Feasibility is decided by the independent benchmark authority, not by JEV.

### Search quality

Report:

- final operating cost;
- Stress Score;
- benchmark feasibility;
- accepted moves;
- exact evaluations;
- iterations.

A result with a better objective but much larger exact-evaluation cost is not
automatically a better selector.

## Interpretation

The most important negative-result rule remains:

> If JEV chooses badly after receiving the information needed to distinguish the
> candidates, that is evidence against the selector. If the required information
> is absent from its features, the result is evidence of an information
> bottleneck instead.

This experiment deliberately records the full candidate labels in test.jsonl
so that those two explanations can be separated.

## Reproducibility

Run:

    python scripts/download_ras_l1.py
    python scripts/run_l1_experiment.py

For the expensive Vanilla baseline:

    python scripts/run_l1_experiment.py --include-vanilla

Do not report these cases as official RAS competition scores.
