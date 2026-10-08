# R1-C — Controlled 8×50 Benchmark Specification

## Status

**Design gate implemented.** The specification below defines the controlled benchmark
before any generator or frozen input is created. The companion instance-design checker
is now implemented and is the first executable gate against this specification.

R1-C is a parallel experimental track. It does **not** replace the historical Nicolas
8×50 provenance track. The latter remains useful for archaeology and reproduction,
but the JEV research program must not depend on recovering an undocumented historical
input file.

## 1. Scientific purpose

The benchmark must answer a narrow question:

> Can a learned local selector choose a small number of promising VLNS actions and
> retain most of the improvement available to the full candidate pool?

The benchmark is therefore designed around **decision surfaces**, not merely around
having 8 yards and 50 demands.

A useful instance must contain states in which:

- more than one candidate action is plausible;
- the best action is not determined by a single scalar such as block volume;
- dropping a block can require non-local rerouting;
- adding a block can improve several commodities through consolidation;
- a Swap can be useful when neither a pure Drop nor a pure Add improves;
- an exact evaluator can distinguish good and bad candidates;
- a small Mixed-Integer Programming (MIP) model can provide an exact or explicitly
  bounded teacher.

MIP means Mixed-Integer Programming: the RBP is expressed with discrete decision
variables and solved by an exact/branch-and-bound optimizer. It is a teacher for the
small controlled instance, not the intended large-scale solver.

## 2. Identity and provenance

The first controlled instance family has the identity:

`R1-C8x50`

The first frozen instance will be:

`R1-C8x50-A`

No file under R1-C8x50 may be described as the Nicolas 8×50 input.

Every frozen instance must record:

- benchmark identity;
- generator version;
- generator seed;
- full generator parameters;
- source commit;
- SHA-256 for every input file;
- schema/validator version;
- creation timestamp.

Historical Nicolas recovery remains documented in
`docs/r1-freeze-8x50.md`.

## 3. Input contract

Use the existing four-file RBP contract:

- `nodes.csv`
- `links.csv`
- `demands.csv`
- `setting.csv`

The controlled generator should emit the benchmark-compatible fields already supported
by JEV-RBP and also preserve the legacy fields required by the archived Nicolas solver.

Where the two layers differ, both representations may be stored, but no field may
silently change meaning.

## 4. Physical network design

### 4.1 Yards

Exactly 8 classification yards:

`A, B, C, D, E, F, G, H`

The generator may map them to integer node IDs, but their semantic roles are fixed:

| Yard role | Purpose |
|---|---|
| A | western feeder / demand origin |
| B | consolidation hub |
| C | western-central classification |
| D | central interchange / alternative hub |
| E | eastern-central classification |
| F | eastern feeder / demand origin |
| G | consolidation hub |
| H | eastern/western bypass yard |

The actual labels are not solver-visible semantic hints; they exist only to make the
design reviewable. Final experiment files use numeric IDs.

### 4.2 Yard heterogeneity

The 8 yards must not be interchangeable.

Required variation:

- at least 2 hump yards;
- at least 2 flat yards;
- at least 3 different `num_tracks` values;
- at least 2 different handling capacities;
- at least 3 different handling costs;
- at least 2 railroad identities;
- at least 2 interchange-capable yards.

The purpose is to prevent JEV from solving the task using only OD distance.

### 4.3 Physical connectivity

The physical graph must be connected and contain:

- a main corridor;
- a secondary corridor;
- at least 2 chord/bypass links;
- at least 6 yard pairs with two physically distinct paths;
- at least 3 such pairs whose second path is within the maximum circuitous ratio
  when compared with the shortest path.

Use the benchmark convention that the physical network is treated as bidirectional
for shortest-path purposes.

### 4.4 Distance bands

The network must contain yard pairs in all three block-volume distance bands:

| Shortest physical distance | Required purpose |
|---|---|
| < 100 miles | short-block cases and direct-only demands |
| 100–500 miles | dominant operating regime |
| > 500 miles | long-block minimum-volume pressure |

The exact link lengths are chosen so that these bands arise naturally from shortest
paths rather than from arbitrary labels.

### 4.5 Capacity bottlenecks

At least:

- 2 physical links must be potential C5 bottlenecks;
- 2 yards must be handling-capacity bottlenecks;
- 3 yards must have meaningful outbound track pressure.

However the instance must still admit at least one fully feasible solution.

## 5. Demand design

Exactly 50 demands.

The base family distribution is:

| Commodity / demand type | Count | Routing rule |
|---|---:|---|
| Merchandise | 20 | unrestricted service paths |
| Coal | 10 | Bulk block semantics |
| Grain | 10 | Bulk block semantics |
| Intermodal | 5 | direct O→D only |
| Automobile | 5 | direct O→D only |

The benchmark therefore exercises both:

- commodity identity; and
- block type (Manifest / Bulk / Intermodal / Multilevel).

A block may not silently carry multiple commodity classes.

### 5.1 Volume bands

Demand volumes must use deliberately separated bands rather than pure random noise.

The family should contain:

- low-volume demands that create consolidation pressure;
- medium-volume demands that can support one direct block;
- high-volume demands that create strong consolidation incentives;
- a small number of values close to the applicable minimum-block thresholds.

The exact volume assignment is produced by the generator under constraints. The
generator must reject a candidate family member if the resulting problem becomes
trivial, infeasible, or dominated by a single OD pair.

### 5.2 OD structure

The 50 demands must be constructed from three interacting patterns:

**Direct markets**

Several OD pairs have enough volume to support a direct block.

**Hub-consolidation markets**

Several OD pairs individually fall below their direct minimum, but their traffic can
share one or more O→H and H→D blocks.

**Competing-hub markets**

At least 4 demand groups have two plausible consolidation hubs. The cheaper choice
must depend on more than shortest distance alone, through some combination of:

- fixed block cost;
- classification handling cost;
- outgoing track pressure;
- physical-link capacity;
- interchange cost.

This is the central mechanism that creates a non-trivial local decision surface.

### 5.3 Direct-only demands

All Intermodal and Automobile demands must have:

- a feasible direct O→D block;
- no valid multi-block alternative in the benchmark semantics;
- sufficient volume for the direct block minimum.

These demands ensure that JEV cannot treat every demand as a generic
hub-routing problem.

## 6. Required search phenomena

The instance is not accepted merely because it is feasible.

After running the canonical candidate generator and exact evaluator, the instance
must demonstrate all of the following somewhere in the baseline search trajectory:

### P1 — Useful Drop

At least one state contains a Drop candidate that is improving and removes a block
whose traffic can be rerouted.

### P2 — Useful Add

At least one state contains an Add candidate that improves total operating cost by
creating consolidation or reducing handling/transport cost enough to justify its
fixed cost.

### P3 — Non-trivial choice

At least one phase must contain at least 3 candidates for which the exact evaluator
produces different outcomes, including at least one improving and one non-improving
candidate.

### P4 — Best candidate not implied by one feature

At least one test state must contain two candidates with similar volume and distance
but materially different exact deltas because their structural context differs.

### P5 — Useful Swap

At least one state must exist in which:

- no Drop improves;
- no Add improves;
- a Swap improves.

This is essential. Without P5, the benchmark does not test the distinctive VLNS
neighborhood.

### P6 — Selector pressure

At least one state must have:

- a complete candidate pool larger than K=1;
- a different best candidate and first-ranked distractor;
- a measurable quality difference between Top-1 and Top-K evaluation.

### P7 — Information boundary

The features available to JEV must be able to distinguish the candidates in P4/P6
without exposing:

- exact objective delta;
- exact feasibility;
- MIP solution membership;
- future search results.

## 7. Initial solution

The primary baseline state is the solution produced by the repository's deterministic
Greedy constructor.

For reproducible selector comparisons:

`same instance + same Greedy state + same candidate generator`

must produce identical candidate menus before selector ranking.

A second optional initial state may come from a deliberately perturbed feasible
solution, but it is not part of the first R1-C acceptance gate.

## 8. Teacher and reference solvers

For R1-C, run four views of the same instance:

| Solver | Role |
|---|---|
| Greedy | deterministic warm-start baseline |
| Vanilla VLNS | full-candidate search baseline |
| MIP | exact/near-exact teacher on the small instance |
| JEV-VLNS | controlled selector experiment |

An Oracle selector is a diagnostic upper bound only. It may rank the full candidate
pool using exact evaluations, but it is not a valid learned-selector competitor.

The archival Nicolas Greedy/VLNS/MIP implementations remain useful for differential
archaeology. Their result is not automatically the same as the benchmark-authority
result when semantics differ.

## 9. Family design

R1-C must eventually be a family rather than one lucky graph.

Initial target:

| Instance | Yards | Demands | Main purpose |
|---|---:|---:|---|
| R1-C8x50-A | 8 | 50 | primary controlled benchmark |
| R1-C8x50-B | 8 | 50 | topology perturbation |
| R1-C8x50-C | 8 | 50 | tighter capacities |
| R1-C8x50-D | 8 | 50 | stronger competing hubs |
| R1-C8x50-E | 10 | 50 | small scale extension |
| R1-C8x50-F | 12 | 100 | stress / transfer test |

The first implementation only needs A. B–F become the generalization ladder.

## 10. Generator contract

The generator must be a **constrained generator**, not a blind random CSV writer.

Conceptually:

`seed + parameters → candidate instance → validate design properties → accept/reject`

The generator must test:

1. schema validity;
2. connected physical graph;
3. all 50 demands present exactly once;
4. valid direct-only demands;
5. existence of a feasible solution;
6. presence of the required P1–P7 search phenomena;
7. MIP tractability;
8. deterministic serialization.

Rejection is preferable to silently relaxing a constraint.

## 11. Freeze protocol

Once an instance is accepted:

`generated → validated → MIP/solver audit → frozen`

The freeze is immutable and non-destructive, following the existing R1 freeze policy.

Store:

```
data/r1-controlled/R1-C8x50-A/
    nodes.csv
    links.csv
    demands.csv
    setting.csv
    manifest.json
```

`manifest.json` must include:

- instance ID;
- generator ID/version;
- seed;
- parameter hash;
- input SHA-256;
- row counts;
- feasibility status;
- Greedy objective;
- Vanilla VLNS objective;
- MIP objective or lower/upper bound;
- MIP gap;
- solver versions;
- acceptance-test summary.

## 12. R1-C acceptance gate

R1-C design is complete when the first instance satisfies all of these:

- exactly 8 yards and exactly 50 demands;
- all five demand types are represented;
- direct-only rules are exercised;
- at least 2 physical bottlenecks exist;
- at least 2 handling bottlenecks exist;
- P1–P7 are observed;
- Greedy produces a feasible starting state;
- Vanilla VLNS terminates reproducibly;
- MIP returns an optimal solution or an explicitly recorded non-zero gap;
- the clean-room evaluator agrees with the declared benchmark authority;
- the instance is frozen with hashes and metadata.

Only after this gate should the repository make a quantitative JEV-vs-VLNS claim
on R1-C.

## 13. What this design deliberately avoids

The first R1-C instance must **not**:

- be presented as Nicolas's lost 8×50 input;
- be tuned directly against a JEV test score;
- leak the MIP optimum into selector features;
- contain only direct one-block demands;
- rely on one symmetric topology;
- be generated solely from unconstrained random numbers;
- be accepted just because Greedy finds some feasible solution.

The scientific objective is a reusable controlled decision benchmark, not a single
hand-tuned demo.

## 14. Next implementation step

Do **not** write the full generator yet.

The next engineering step is to implement a small **instance-design checker** from
this specification. It should operate on any candidate four-file dataset and report
which R1-C properties and P1–P7 conditions pass or fail.

Only after that checker exists should the constrained generator be written.
