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
