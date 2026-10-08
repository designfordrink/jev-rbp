# R1-C instance-design checker

## Purpose

The checker is the first engineering gate for the controlled benchmark track.

It validates **design-time properties** of a candidate R1-C instance before the
expensive generator/solver loop is introduced.

It intentionally does not claim that a candidate has useful VLNS behavior merely
because its CSV files look plausible.

## Run

From the repository root:

```bash
python scripts/check_r1_instance.py /path/to/instance
```

For machine-readable output:

```bash
python scripts/check_r1_instance.py /path/to/instance --json
```

R1-C accepts both the clean-room filenames:

```
node.csv
link.csv
demand.csv
setting.csv
```

and the historical/archive aliases:

```
nodes.csv
links.csv
demands.csv
settings.csv
```

## What it checks

The checker separates inexpensive structural checks from dynamic search evidence.

### Static design checks

It checks:

- input/schema integrity and unique node/link/demand identifiers;
- exactly 8 yards;
- exactly 50 demands;
- 20 Merchandise + 10 Coal + 10 Grain + 5 Intermodal + 5 Automobile;
- yard heterogeneity: yard types, track counts, handling capacities/costs,
  railroad identities and interchange yards;
- physical-network connectivity;
- at least two independent cycle/chord structures;
- at least 6 yard pairs with an alternative physical path;
- at least 3 of those alternative paths within the configured maximum
  circuitous ratio;
- all three shortest-distance bands;
- feasible direct-only Intermodal/Automobile demands;
- direct-market, consolidation-market and competing-hub structure;
- demand-weighted **potential** physical-link and yard bottlenecks.

The bottleneck calculation is deliberately a design-time proxy: it routes each
demand on its physical shortest path and compares the resulting load with link
capacity / yard handling capacity. It is **not** a replacement for exact C3/C5
validation.

### Dynamic checks P1–P7

The following cannot be established from the CSV input alone:

- P1 — useful Drop;
- P2 — useful Add;
- P3 — non-trivial candidate choice;
- P4 — similar cheap features, different exact deltas;
- P5 — useful Swap when Drop and Add do not improve;
- P6 — selector pressure / Top-K effect;
- P7 — information boundary is sufficient.

The checker therefore accepts an optional evidence JSON.

Example shape:

```json
{
  "instance_id": "R1-C8x50-A",
  "phenomena": {
    "P1": {
      "observed": true,
      "summary": "Drop block 17 improved the exact objective.",
      "phase_id": "it03-drop"
    }
  }
}
```

All P1–P7 must have `observed: true` for the dynamic portion of the design
gate to become PASS.

## Exit semantics

- `PASS` — all required checks passed;
- `FAIL` — at least one required check failed;
- `INCOMPLETE` — static design checks pass, but one or more required dynamic
  checks are still `NOT_EVALUATED`.

This is intentional. It prevents a visually plausible 8×50 CSV from being
mistaken for a scientifically useful JEV benchmark.

## Architecture boundary

```
R1-C generator
      |
      v
instance-design checker
      |
      v
Greedy / Vanilla VLNS / MIP audit
      |
      v
P1–P7 evidence
      |
      v
freeze
      |
      v
JEV experiment
```

The checker is outside the JEV selector path and never reads JEV scores or exact
candidate deltas unless they are supplied as explicit evidence after a search
audit. It does not change the candidate generator or evaluator.

## Implementation

The implementation is in:

```
src/jev_rbp/r1_design_checker.py
```

The CLI wrapper is:

```
scripts/check_r1_instance.py
```

Unit tests are in:

```
tests/test_r1_design_checker.py
```
