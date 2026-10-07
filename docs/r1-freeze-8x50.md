# R1 — Freeze the Nicolas 8×50 reference instance

The first reconstruction target is the toy instance used by Nicolas Bridelance's saved MIP and VLNS notebooks: **8 yards / 50 commodities**.

## Current status: BLOCKED on exact source input\n\nFreeze tooling is now implemented and covered by tests. The blocker is only acquisition of the original four CSV files.

The repository contains the archived solver implementation and saved notebooks, but **does not currently contain the four source CSV files used by the notebook run**:

- `nodes.csv`
- `links.csv`
- `demands.csv`
- `setting.csv`

The notebooks call `load_rail_network(DATA_DIR)`; they do not generate the 8×50 instance themselves, and their saved cells contain no executed output from which the input can be reconstructed.

The archived solver package is therefore **not sufficient by itself to claim that we have reproduced Nicolas's 8×50 result**.

### Important rule

Do **not** create a synthetic 8×50 instance and label it the Nicolas reference instance. A synthetic instance may be useful later as a separate test fixture, but it must have a different identity.

## What we have

- `data/reference/railroad-blocking-mip-pyomo-highs.ipynb`
- `data/reference/railroad-blocking-vlns-metaheuristic.ipynb`
- `data/reference/rbp-solver-utils.zip`
- `data/reference/archive/` — provenance copy of the reference loader, evaluator, validator, Greedy, VLNS and MIP implementations.

The notebooks identify the expected scale (8 yards / 50 commodities), but the input files are not embedded in them.

## Freeze protocol

Once the exact source directory is found, run (the tool now exists at `scripts/freeze_reference_instance.py`):

```bash
python scripts/freeze_reference_instance.py \
  --source /path/to/exact/nicolas/toy/data \
  --output data/reference/reconstruction/8x50
```

The freezer performs **no normalization, filtering, sorting or regeneration**.

It requires:

- exactly 8 rows with `node_type=yard`;
- exactly 50 commodity rows in `demands.csv`;
- all four required CSV files.

It copies the files byte-for-byte and creates `manifest.json` with SHA-256 hashes.

## R1 acceptance criteria

R1 is complete only when:

1. the exact source directory has been identified;
2. the freezer succeeds with 8 yards / 50 commodities;
3. the four input hashes are recorded;
4. Greedy, VLNS and MIP can all load the frozen directory;
5. their outputs, objective, feasibility, runtime and solver parameters are captured by `scripts/run_reference_reconstruction.py`.

Until these conditions are met, **no numerical claim about reproducing the Nicolas reference result should be made**. The freeze tests use an explicitly synthetic temporary fixture; they are software tests, not the R1 reference data.

## Next acquisition targets

Search in this order:

1. the original Kaggle notebook's attached **competition input**;
2. the public `rbp-railroad-blocking-utils` dataset/version metadata;
3. downloaded Kaggle notebook output/session artifacts;
4. any local Kaggle/Colab/Jupyter working directory used when the notebook was executed;
5. only after exhausting the above, construct a clearly labelled synthetic micro-instance for software testing.

The target is the **original input**, not merely any dataset on which the archived solver can run.

## Provenance audit — Kaggle notebooks

The three Nicolas Bridelance notebooks were checked as the authoritative notebook references for R1:

- MIP: https://www.kaggle.com/code/nbridelancetb/railroad-blocking-mip-pyomo-highs
- EDA + Greedy: https://www.kaggle.com/code/nbridelancetb/railroad-blocking-eda-greedy-baseline
- VLNS: https://www.kaggle.com/code/nbridelancetb/railroad-blocking-vlns-metaheuristic

They point to the Kaggle dataset **RBP Railroad Blocking - Solver Utilities**:

- https://www.kaggle.com/datasets/nbridelancetb/rbp-railroad-blocking-utils

This is important because it gives us the provenance target: the historical R1 inputs must be recovered from the dataset/version attached to these notebooks, rather than from the current competition data.

### What the Kaggle pages establish

- The notebooks are Nicolas Bridelance's MIP, EDA/Greedy, and VLNS reference notebooks.
- The notebook input is the **RBP Railroad Blocking - Solver Utilities** dataset.
- The repository's `data/reference/archive/` is a provenance copy of the solver-side code, not a copy of the notebook input dataset.
- The exact historical CSV payload is still not exposed by the Kaggle page HTML available to our tooling. Therefore the exact 8×50 CSV contents have **not** been independently recovered yet.

### What we must not infer

The current INFORMS RAS 2026 competition data page is a different artifact:

- https://www.kaggle.com/competitions/informs-ras-2026-problem-solving-competition/data

Its current L1/L2/L3 instances are not evidence for the historical 8×50 notebook input. Do not substitute them for R1.

Likewise, the existence of `nodes.csv`, `links.csv`, `demands.csv`, and `setting.csv` in the solver/data model tells us the expected four input roles, but does not by itself prove that a particular downloaded version is Nicolas's 8×50 run.

## Exact acquisition procedure

The next reproducible acquisition attempt should be performed with authenticated Kaggle CLI/API access, because the public notebook HTML/API surface available here does not expose the dataset file payload.

Record the exact dataset version before copying anything:

```bash
kaggle datasets files -d nbridelancetb/rbp-railroad-blocking-utils
```

Then download the identified version into a temporary directory, preserving the original archive/file names:

```bash
mkdir -p data/reference/reconstruction/_acquisition
kaggle datasets download \
  -d nbridelancetb/rbp-railroad-blocking-utils \
  -p data/reference/reconstruction/_acquisition
```

If the dataset exposes multiple versions, repeat the download for each candidate version and record the version number, archive SHA-256, and extracted file list. Do **not** run the freeze tool until a candidate contains an 8-yard / 50-commodity input.

For each candidate, inspect:

```text
nodes.csv
links.csv
demands.csv
setting.csv
```

and record:

- exact dataset/version identifier;
- exact filenames;
- row counts;
- number of `node_type=yard` rows;
- demand/commodity row count;
- SHA-256 of every CSV;
- whether the reference loader accepts the directory unchanged.

Only a candidate satisfying the 8×50 acceptance condition can be promoted to `data/reference/reconstruction/8x50/`.

### Current conclusion

**The R1 question is now narrowed to dataset-version recovery.** We have the three reference notebooks, the named Kaggle input dataset, and the reference solver archive. The remaining missing artifact is the exact historical input payload/version used for the 8×50 run.

No synthetic replacement has been promoted, and no numerical reproduction claim has been made.

## Candidate audit tool

A downloaded Kaggle dataset/archive can now be checked without modifying or promoting it:

```bash
python scripts/audit_kaggle_candidate.py /path/to/downloaded/archive.zip
python scripts/audit_kaggle_candidate.py /path/to/extracted/directory --json
```

The auditor searches recursively for the four expected input files, validates the R1 shape (8 yard rows and 50 demand rows), and reports byte size plus SHA-256 for each CSV. A candidate is **not** promoted automatically. Promotion still requires provenance confirmation that it is the historical dataset/version attached to Nicolas's notebook.
