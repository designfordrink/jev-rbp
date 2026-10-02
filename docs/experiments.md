# Experiments

All experiments must be controlled experiments, not ad-hoc solver runs.

## Required run metadata

Every run should record:

- git commit;
- dataset/version;
- instance id;
- random seed;
- initial solution identifier;
- selector;
- candidate-generator configuration;
- K;
- evaluation budget;
- time limit;
- Python and solver versions;
- hardware.

## Core comparison

For a fixed instance and initial state:

| Selector | Candidate set | Exact evaluator | Validator | Budget |
|---|---|---|---|---|
| Random | same | same | same | same |
| Greedy | same | same | same | same |
| Vanilla VLNS | same | same | same | same |
| JEV Top-K | same | same | same | same |

Only the selector should change.

## Primary measurements

### Search efficiency

- exact evaluations;
- candidate evaluations;
- iterations;
- accepted moves;
- runtime.

### Solution quality

- objective;
- objective components;
- gap where an oracle/reference is available.

### Selector quality

- top-1 hit rate;
- top-K recall;
- rank of the best action;
- regret.

## Important interpretation rule

A better objective with ten times more exact evaluations is not automatically a better selector.

The first JEV experiment should therefore report quality together with search cost.
