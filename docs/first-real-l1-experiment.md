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

The first controlled run uses a clearly documented active-yard subset and retains the complete physical network. This is a real-data prototype slice, not an official competition score.

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

## First executed result

Run date: 2026-10-04.

The first successful GitHub Actions run used:
- 6 selected L1 demands;
- 4 train demands / 2 test demands;
- 6 active yards in train / 4 active yards in test;
- 1 offline dataset iteration;
- 2 search iterations;
- K=1, 5, 10 exact evaluations per phase;
- selectors: Identity, Random, RBP Greedy and Linear JEV.

The RAS L1 download completed successfully and the published link.csv.zip
SHA-256 matched:

    db9a6f2900e5011d632567882f91fbb7a42f19a40e2450fd0c2e8733a4d62e37

The training dataset contained 134 exact candidate labels.

Observed test results:

| Selector | K | Exact evals | Operating cost | Stress Score | Feasible |
| --- | ---: | ---: | ---: | ---: | --- |
| Identity | 1/5/10 | 3/12/22 | 5000.00 | 13631418.58 | no |
| Random | 1/5/10 | 3/12/22 | 5000.00 | 13631418.58 | no |
| RBP Greedy | 1/5/10 | 3/12/22 | 5000.00 | 13631418.58 | no |
| Linear JEV | 1/5/10 | 3/12/22 | 5000.00 | 13631418.58 | no |

### Interpretation

This is a negative result, not evidence that the selectors are equivalent.

All selectors started from the same simple direct-block seed and none found an
accepted improving move that produced a benchmark-feasible final solution on
this tiny test slice. Consequently the final operating cost remained at the
seed-level value of 5000.00 and all selector rankings collapsed to the same
result.

The most important next task is therefore not to tune Linear JEV. We first
need a valid/meaningful experimental seed and a test slice on which at least
some candidate moves can improve the benchmark-authoritative result. Otherwise
the selector has no useful signal to learn from.

This also reveals a performance characteristic: even the 6-demand slice took
about 67 seconds to execute because exact move evaluation repeatedly performs
routing over the full physical L1 network. A larger experiment should therefore
add routing/evaluation reuse or another explicit computational budget before
increasing the number of demands.

## Run the first controlled experiment

After preparing the public inputs:

    python scripts/download_ras_l1.py

run:

    python scripts/run_l1_experiment.py

The current reproducible GitHub Actions workflow is manual-only:
.github/workflows/real-l1-experiment.yml.

It uses the small first-experiment configuration above. The workflow uploads
artifacts/l1-first-experiment/ containing:

- train.jsonl — exact offline training labels;
- model.json — fitted Linear JEV model;
- config.json — selected demand IDs and experiment settings;
- results.csv and results.json — selector results.

### Important interpretation rule

The train/test split is over demand rows while the physical L1 network is
shared. Therefore this experiment tests the integration of JEV with real RBP
data and gives a first ranking signal, but it is not an independent-instance
generalization experiment and must not be reported as an official RAS score.

The public RAS v2.1 release describes the archived L1 input as 47,193 nodes,
106,570 links and 2,044 demand rows. The upstream repository also explicitly
distinguishes those archived-file statistics from the published competition
design table. See the upstream release and README before comparing results with
official benchmark cases.
