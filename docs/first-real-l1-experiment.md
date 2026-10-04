# First real RAS L1 experiment

The first real-data experiment uses the public RAS2026-PSC v2.1 L1 dataset.

The upstream release reports:
- L1 network: 47,193 nodes and 106,570 links;
- archived L1 demand: 2,044 rows;
- official demand multipliers: 0.5x, 1.0x and 2.0x.

The repository deliberately does not vendor these large benchmark files.

## Prepare data

Run:

    python scripts/download_ras_l1.py

This creates data/ras2026-v2.1/l1/ with node.csv, link.csv, link.csv.zip, demand.csv and setting.csv.

The script verifies the published SHA-256 of link.csv.zip.

## Candidate-universe constraint

The default RBPMoveGenerator preserves the clean-room reference behavior and considers every yard pair with a physical route.

For experiments on the full L1 network this candidate universe is too large for an initial JEV prototype. RBPMoveGenerator therefore accepts an optional candidate_yards set. This is an experiment-time restriction; it does not change the default behavior.

The first controlled run should use a clearly documented active-yard subset and retain the complete physical network. This is a real-data prototype slice, not an official competition score.

Do not mix results from such slices with official L1/L2/L3 benchmark scores.

## Scientific sequence

1. Freeze the RAS v2.1 data hash and experiment configuration.
2. Build the same initial solution for every selector.
3. Use the same candidate pool and exact evaluator.
4. Compare Identity, Random, RBP Greedy and Linear JEV.
5. Run K=1, K=5 and K=10 exact evaluations per phase.
6. Keep Oracle only as an upper bound.
7. Record objective, Stress Score, feasibility and exact-evaluation count.

A real generalization claim requires independent instances. Demand slices from the same L1 instance are useful for debugging and ranking experiments, but they must not be described as independent train/test instances.
