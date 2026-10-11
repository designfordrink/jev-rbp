# R1-C constrained generator — first implementation

## Purpose and current status

`scripts/generate_r1_instance.py` creates a deterministic first-pass 8-yard / 50-demand candidate and immediately runs the static design checker. It is a deterministic structured candidate generator, not yet a validated or frozen benchmark.

Run from the repository root:

```bash
python scripts/generate_r1_instance.py --seed 20261009 --output data/R1-C8x50-A
```

A different integer seed changes the non-Merchandise OD/volume assignments and demand ordering. The four structured Merchandise markets are fixed so that the required competing-hub pattern is not left to chance. The physical topology and yard-role table are fixed in generator version 0.1.0, so seed comparisons are not independent topology samples.

## Acceptance boundary

- The generator invokes the checker with `--static-only`, so a non-zero exit means a static design requirement failed and the candidate must not be frozen. Without that flag, the checker also requires P1–P7 dynamic evidence and will remain incomplete until an evidence file is supplied.
- A static `PASS` only means the design-time checks passed.
- P1–P7 (useful Drop/Add/Swap, non-trivial choice, selector pressure, and information-boundary evidence) still require search traces and exact evaluations.
- A solver/benchmark audit must independently establish that a feasible solution exists and that the instance is meaningful for VLNS.
- The generated manifest records file SHA-256 values, seed, generator version and provenance. Do not edit the CSV files after generation without regenerating the hashes.

## Current limitations — do not overclaim

Version 0.2.0 uses a fixed hand-authored topology and deliberately constructs four competing-hub Merchandise markets. Remaining demand classes are seeded. It still does not search/repair the topology or parameter space, guarantee solver feasibility, or demonstrate P1–P7. If the checker rejects a candidate, the next implementation task is to improve the generator using the failed-check report rather than weakening the checker.

The first output directory is named `R1-C8x50-A` for workflow convenience only. It is **not a frozen accepted benchmark** until static checks pass, the canonical Greedy / Vanilla VLNS / MIP audit is completed, P1–P7 evidence is attached, and the manifest/provenance are reviewed.
