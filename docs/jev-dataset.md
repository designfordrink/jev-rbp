# JEV dataset

Phase 7 records the local decisions made available to a JEV selector.

## Label definition

For every reached VLNS phase, the generator emits the complete deterministic
candidate pool. Every candidate is evaluated with the same exact evaluator.
Each row stores:

- phase and iteration;
- deterministic candidate index;
- typed action and payload;
- cheap state/action features;
- feasibility;
- objective before and after;
- exact objective delta;
- an `is_improving` label.

The exact delta is the training target. A negative delta means that the action
reduces the objective.

## Important boundary

The feature extractor must not call the exact evaluator. Features are cheap
observations available before the expensive evaluation. Feasibility and delta
are labels produced by the authoritative evaluator.

The dataset generator replays the recovered Drop → Add → conditional Swap
control flow and applies the exact best improving move between phases. Therefore
the rows describe the local decision surface encountered by the baseline VLNS,
not arbitrary independent states.

## Reproducibility

Generation is deterministic when the instance, initial solution, candidate
generator, evaluator, and feature extractor are deterministic.

The dataset should later be split by **instance**, not by row. Rows from one
instance are highly correlated because they come from the same search trajectory.

## Current RBP features

The built-in extractor includes:

- phase one-hot flags;
- candidate index;
- number of open blocks;
- number of demands;
- Drop block volume;
- physical distance for Drop/Add;
- outgoing block degree at relevant yards.

These are deliberately simple baseline features. They can be extended without
changing the exact evaluator or selector protocol.

## Output

`write_jsonl()` writes one JSON object per line, making datasets easy to
inspect, diff, stream, and process with Python or other ML tooling.
