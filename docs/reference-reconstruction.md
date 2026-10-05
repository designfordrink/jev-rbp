# Reference Reconstruction

## Purpose

Before making a scientific claim about JEV, establish a reproducible reference
point from Nicolas Bridelance's public Railroad Blocking work.

The reference point is not a new competitor. It is the **zero point** against
which the clean-room JEV-RBP implementation is validated.

The reconstruction has three reference solvers:

1. **Greedy** — a fast constructive baseline and the usual VLNS warm start.
2. **VLNS** — Very Large Neighborhood Search, the scalable local-search baseline.
3. **MIP** — Mixed-Integer Programming, an exact optimization formulation for
   small instances; with a sufficiently small optimality gap it provides an
   optimum or near-optimum teacher.

## Scientific question

The first question is not:

> Does JEV get a lower final cost?

It is:

> Can JEV preserve the search quality of the reference VLNS while reducing
> the number of expensive exact candidate evaluations?

This distinction is essential because vanilla VLNS evaluates the complete
candidate pool, while JEV is intended to rank candidates cheaply and send only
Top-K candidates to the exact evaluator.

## Frozen reference chain

```
Nicolas reference materials
        |
        +--> Greedy
        |
        +--> VLNS
        |
        +--> MIP (small instances)
        |
        v
REFERENCE BASELINE
        |
        v
clean-room implementation
        |
        v
differential comparison
        |
        v
controlled JEV experiment
```

The archived reference implementation remains under
`data/reference/archive/` and is treated as provenance material. The
production implementation under `src/jev_rbp/` remains clean-room code.

## Source inventory

The repository currently contains:

- `data/reference/railroad-blocking-vlns-metaheuristic.ipynb`
- `data/reference/railroad-blocking-mip-pyomo-highs.ipynb`
- `data/reference/rbp-solver-utils.zip`
- `data/reference/archive/data_loader.py`
- `data/reference/archive/evaluator.py`
- `data/reference/archive/io_json.py`
- `data/reference/archive/validator.py`
- `data/reference/archive/solvers/greedy.py`
- `data/reference/archive/solvers/vlns.py`
- `data/reference/archive/solvers/mip.py`

The archived solver files are particularly important because they expose the
actual search and evaluation logic rather than only notebook presentation.

## Phase R0 — Freeze provenance

Record, for every reproduction:

- repository commit;
- reference file hashes;
- input-instance identity;
- solver name and parameters;
- time limit;
- MIP gap where applicable;
- random seed where applicable;
- output solution;
- objective;
- feasibility;
- runtime;
- solver-specific trace.

No result should be called a reference result without this metadata.

## Phase R1 — Reproduce the reference input

Find a deterministic, small instance that can be executed by all three
reference paths.

Priority:

1. the smallest instance already used by the Nicolas notebook;
2. a frozen subset derived from the public RAS data if necessary;
3. only then a larger L1 case.

The first instance must be small enough that MIP can be used as an exact or
near-exact teacher.

## Phase R2 — Reproduce Greedy

Run the archived Greedy implementation and record:

- opened blocks;
- blocking sequences;
- physical routes;
- feasibility;
- benchmark/reference objective;
- runtime.

Greedy is a baseline, not the main scientific target.

## Phase R3 — Reproduce reference VLNS

Run the archived VLNS with its original control flow.

The verified behavior is:

```
iteration
  -> best Drop
  -> apply if improving
  -> best Add
  -> apply if improving
  -> only if neither improved: best Swap
  -> stop if no improvement
```

A single iteration may therefore contain both a Drop and an Add.

Record:

- initial solution;
- every accepted move;
- candidate counts by phase;
- exact evaluations;
- objective before/after each move;
- final blocks;
- final routes/sequences;
- runtime;
- termination reason.

## R4 — Reproduce MIP

Run the archived Pyomo + HiGHS formulation on the same small instance.

MIP means **Mixed-Integer Programming**: the optimization problem is written
with discrete decision variables and solved by an exact/branch-and-bound
optimizer.

Record:

- objective;
- lower bound;
- optimality gap;
- runtime;
- feasibility;
- selected blocks and sequences.

If MIP proves optimality, the result becomes the strongest local-instance
reference. If it reaches a time limit with a nonzero gap, it is explicitly
labelled a near-optimal bound rather than an optimum.

## R5 — Differential comparison

Compare the archived reference solver and `src/jev_rbp/` at increasing
granularity:

1. candidate universe;
2. candidate identity;
3. initial solution;
4. move ordering;
5. routing result;
6. objective delta;
7. feasibility decision;
8. accepted move;
9. termination;
10. final solution.

A final objective match alone is insufficient: two different search paths can
accidentally finish at the same cost.

### Tolerance policy

Floating-point objective values are compared with an explicit absolute and
relative tolerance. Discrete structures such as block IDs, move type and
accept/reject decision are compared exactly unless the reference itself leaves
a tie unresolved.

Equal-cost ties must be recorded rather than silently normalized.

## R6 — Establish the JEV zero-point experiment

Only after R5 is green:

```
same instance
same initial solution
same candidate generator
same exact evaluator
same validator
same acceptance rule
        |
        +--> Vanilla: evaluate all candidates
        |
        +--> Random: evaluate K candidates
        |
        +--> Greedy: evaluate K candidates
        |
        +--> Linear JEV: evaluate K candidates
        |
        +--> Oracle@K: diagnostic upper bound only
```

Measure K = 1, 2, 5, 10, 20, 50, all where computationally practical.

The main graph is:

**solution quality vs exact evaluations / compute budget**.

## What counts as success

The first successful milestone is not a better benchmark score.

It is:

1. reproducible Nicolas reference run;
2. clean-room implementation agrees with it within declared tolerances;
3. MIP agrees on the small instance or provides a documented bound;
4. JEV experiments change only candidate selection;
5. JEV's quality/compute curve can be measured.

Only then should more expressive JEV models or LLM-generated heuristics be
introduced.

## Known non-equivalences to resolve

The current archaeology documents several places requiring explicit checking:

- exact tie-breaking;
- exact candidate enumeration order;
- historical reference move-level C2/C4a gates versus full RAS v2.1 validation;
- historical interchange treatment;
- physical link capacity interactions;
- reference notebook input/output conventions;
- whether notebook and archived utility versions are byte-for-byte aligned.

These are research questions, not assumptions. Each discrepancy gets recorded
with evidence and a decision.

## Deliverables

The Reference Reconstruction stage is complete only when the repository has:

- a frozen reproduction instance;
- a reproducible reference run;
- a reference result record;
- a differential comparison report;
- tests for the discovered equivalence rules;
- a documented list of remaining non-equivalences.

