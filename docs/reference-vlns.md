# Reference VLNS Archaeology

## Purpose

This document records the verified behavior of the public Nicolas Bridelance Railroad Blocking VLNS notebook and maps it to the JEV-RBP architecture.

Reference:
- [Railroad Blocking VLNS Metaheuristic](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-vlns-metaheuristic)
- [Railroad Blocking MIP Pyomo HiGHS](https://www.kaggle.com/code/nbridelancetb/railroad-blocking-mip-pyomo-highs)

The Kaggle notebook is the behavioral reference for v0.1. We do **not** claim that its internal source files are directly reusable: the public artifact is a Kaggle notebook, not a standalone source repository.

## 1. Verified search loop

The reference VLNS starts from a greedy solution and repeatedly searches local modifications.

At each iteration it considers three move families:

1. **Drop** — close one block and reroute affected commodities through alternative open blocks.
2. **Add** — open one block and reroute suitable commodities through it.
3. **Swap** — combine a Drop and an Add.

The search uses a **best-improving / steepest-descent** policy: evaluate the available moves and apply the best improving move. Search terminates when no improving move remains or the configured budget is exhausted.

Conceptually:

```text
initial greedy solution
        |
        v
generate Drop / Add / Swap moves
        |
        v
evaluate moves
        |
        v
choose best improvement
        |
        +---- improvement ----> apply move ----> repeat
        |
        +---- no improvement -> stop
```

## 2. Routing

For a candidate blocking design, commodity routing is performed independently using shortest-path search over the open-block service graph.

The reference notebook describes Dijkstra-based routing with an arc cost combining transport distance and handling at intermediate yards:

```text
c(k,i,j) = transport_cost * distance(i,j)
         + handling_cost(j) * [j != destination(k)]
```

This is an important boundary in JEV-RBP:

- routing is an **exact/authoritative evaluation component**;
- JEV may rank candidate actions;
- JEV must not replace the routing calculation in v0.1.

## 3. Objective

The operating objective contains the benchmark's cost components:

- fixed block cost;
- transportation cost;
- classification handling cost;
- interchange cost.

For move selection, JEV-RBP should expose the authoritative:

```text
delta = objective_after - objective_before
```

The selector predicts/ranks; the exact evaluator decides.

## 4. Candidate families

| Reference behavior | JEV-RBP component |
|---|---|
| Drop | `DropAction` |
| Add | `AddAction` |
| Swap | `SwapAction` |
| Dijkstra routing | `RoutingEngine` |
| objective calculation | `ExactEvaluator` |
| feasibility checks | `Validator` |
| best-improving loop | `VLNSSolver` |
| move logging | `TraceRecorder` |

The mapping is architectural, not a claim that the reference implementation has these exact class names.

## 5. Proposed JEV-RBP function map

```text
VLNSSolver.solve(instance, initial_solution)
    |
    +--> CandidateGenerator.generate(state)
    |       |
    |       +--> Drop actions
    |       +--> Add actions
    |       +--> Swap actions
    |
    +--> Selector.rank(state, candidates)
    |
    +--> ExactEvaluator.evaluate(state, action)
    |       |
    |       +--> routing
    |       +--> objective
    |
    +--> Validator.validate(solution)
    |
    +--> acceptance / termination
```

For the first reproduction, `Selector` should be an exact best-improvement selector. This is the baseline against which Random, Greedy and JEV are later compared.

## 6. What is *not* yet verified

The public notebook description is sufficient to reconstruct the algorithmic behavior, but not sufficient to claim byte-for-byte or function-for-function source compatibility.

The following therefore remain archaeology targets:

- exact Python function names and signatures;
- exact internal solution data structures;
- exact candidate-generation filters;
- tie-breaking;
- exact routing cache behavior;
- precise handling/interchange implementation details;
- exact stopping interaction between iteration and wall-clock limits;
- all implementation-level optimizations.

These must be recovered from the notebook source/runtime before claiming reproduction.

## 7. MIP relationship

The public MIP notebook is a separate reference implementation. It is useful as a small-instance oracle and for understanding candidate block generation.

It should **not** be mixed into the vanilla VLNS reproduction. The first baseline should reproduce the heuristic search independently.

## 8. Reproduction principle

The first implementation should preserve this separation:

```text
Problem model
   |
Candidate generation
   |
Exact evaluation
   |
Validator
   |
VLNS acceptance
```

Only after this baseline is reproducible should JEV be inserted between candidate generation and exact evaluation.

## 9. Provenance

Reference notebooks:
- Nicolas Bridelance, *Railroad Blocking VLNS Metaheuristic*, Kaggle, version 9 as currently exposed publicly.
- Nicolas Bridelance, *Railroad Blocking MIP Pyomo HiGHS*, Kaggle, version 9 as currently exposed publicly.

Benchmark specification:
- INFORMS RAS 2026 Problem Solving Competition, v2.1 benchmark package.
- Public mirror: `asu-trans-ai-lab/RAS2026-PSC`.

## 10. Important benchmark distinction

The official benchmark has additional validation rules beyond the early v1.1 package, including direct-block enforcement for Intermodal/Automobile and demand-volume consistency. JEV-RBP therefore uses the released current validator contract as its correctness authority rather than reproducing an old validator bug.

The current competition documentation describes Intermodal and Automobile as direct-only, while a historical v1.1 discussion reported that the early validator did not enforce that rule. The current architecture must use the corrected contract.
