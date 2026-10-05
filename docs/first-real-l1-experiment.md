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

After fixing the direct-block seed, the first meaningful real-data run used:
- 12 selected L1 demands that passed individual direct-seed feasibility checks;
- 8 train demands / 4 test demands;
- 12 active yards in train / 8 active yards in test;
- 1 offline dataset iteration;
- 2 search iterations;
- K=1, 5, 10 exact evaluations per phase;
- selectors: Identity, Random, RBP Greedy and Linear JEV.

The RAS L1 download completed successfully and the published link.csv.zip
SHA-256 matched:

    db9a6f2900e5011d632567882f91fbb7a42f19a40e2450fd0c2e8733a4d62e37

The training dataset contained 1,124 exact candidate labels. The separate test
ranking dataset contained 264 exact candidate labels.

### Final-search result

| Selector | K | Exact evals | Operating cost | Stress Score | Feasible |
| --- | ---: | ---: | ---: | ---: | --- |
| Identity | 1 | 3 | 7,261,129.02 | 7,261,129.02 | yes |
| Random | 1 | 3 | 7,261,129.02 | 7,261,129.02 | yes |
| RBP Greedy | 1 | 3 | 7,261,129.02 | 7,261,129.02 | yes |
| Linear JEV | 1 | 3 | 7,261,129.02 | 7,261,129.02 | yes |
| Identity | 5 | 14 | 7,261,129.02 | 7,261,129.02 | yes |
| Random | 5 | 14 | 7,261,129.02 | 7,261,129.02 | yes |
| RBP Greedy | 5 | 14 | 7,261,129.02 | 7,261,129.02 | yes |
| Linear JEV | 5 | 14 | 7,261,129.02 | 7,261,129.02 | yes |
| Identity | 10 | 24 | 7,261,129.02 | 7,261,129.02 | yes |
| Random | 10 | 24 | 7,261,129.02 | 7,261,129.02 | yes |
| RBP Greedy | 10 | 24 | 7,261,129.02 | 7,261,129.02 | yes |
| Linear JEV | 10 | 24 | 7,261,129.02 | 7,261,129.02 | yes |

No selector accepted an improving move in this slice, so final-search quality
cannot distinguish the four selectors yet.

### Local ranking result

The new ranking diagnostic evaluates whether Linear JEV ranks the exact best
candidate near the top of each reached candidate pool.

| K | Pools with feasible candidates | Top-K hit rate | Mean regret |
| ---: | ---: | ---: | ---: |
| 1 | 1 | 1.000 | 0.000000 |
| 5 | 1 | 1.000 | 0.000000 |
| 10 | 1 | 1.000 | 0.000000 |

This is a useful sanity check, but **not evidence of JEV superiority**: only one
candidate pool contained a feasible candidate suitable for the ranking metric.
The next experiment must deliberately generate more independent candidate
pools and, ideally, some genuinely improving moves.

### What we learned

1. The initial direct seed must be benchmark-complete, including blocking
   sequences; otherwise C1 makes every final result invalid.
2. The seed must also satisfy basic direct-block minimum-volume and link-capacity
   constraints before it is used for selector comparison.
3. On the current real L1 slice, the direct seed is feasible but already locally
   strong enough that no selector improved it.
4. The current exact evaluator is expensive: the 12-demand experiment took
   several minutes because candidate evaluation repeatedly routes over the full
   physical L1 network.
5. Linear JEV's first ranking sanity check is promising but statistically
   meaningless at one feasible pool.

The next scientific step is therefore to construct a set of small but
non-trivial L1 instances/seeds where multiple candidate actions are feasible
and at least some actions have different exact deltas. Only then should we
compare JEV against RBP Greedy and Random as a selector.

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


## Second experiment: non-trivial local search seed

The redundant-block experiment completed successfully, but it exposed an
important issue in the JEV input contract rather than producing a useful final
search improvement.

The seed contains two identical direct blocks for selected demands, while each
demand sequence uses only one. In principle, dropping the unused duplicate is
an improving move because it removes a fixed block cost without making the
demand unroutable.

The experiment nevertheless produced zero accepted moves for all selectors.
The likely explanation is now clear from the selector interface: the original
feature set did not tell JEV whether a candidate block was actually used by a
demand. A used block and an unused duplicate could therefore look almost
identical to the learned selector.

This is an **input-contract problem**, not evidence that JEV cannot rank the
action.

The follow-up change adds cheap state-aware features:

- number of demands using the dropped block;
- volume carried by the dropped block;
- whether the dropped block is unused;
- direct demand count for an Add candidate;
- direct demand volume for an Add candidate.

The ranking metric was also corrected so that tied candidates with the same
optimal exact delta all count as valid Top-K hits.

See `docs/jev-action-selection-contract.md` for the full JEV input contract,
candidate menu, proposed LLM prompt, and the distinction between JEV-0,
JEV-1, and future relational JEV-2.

### Why this matters

A JEV experiment must distinguish:

1. JEV received enough information but chose badly;
2. JEV did not receive the information needed to choose correctly.

Only the first is evidence against the selector.

Therefore the next experiment should explicitly record:

- candidate menu;
- features exposed to JEV;
- JEV ranking;
- exact evaluations of selected candidates;
- optimal exact ranking.

If the state-aware JEV-1 still fails on the controlled redundant-block
test, then we should investigate the ranking model or candidate-budget logic.
If it succeeds, we can move to a multi-demand consolidation seed, where the
selector must reason about sharing and rerouting rather than merely removing
an unused duplicate.

