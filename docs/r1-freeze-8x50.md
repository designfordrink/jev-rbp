# R1 — Freeze the Nicolas 8×50 reference instance

The first reconstruction target is the toy instance used by Nicolas Bridelance's
saved MIP and VLNS notebooks: **8 yards / 50 commodities**.

The notebooks do not generate this instance. They call the archived
`load_rail_network(DATA_DIR)`, which expects four CSV files:

- `nodes.csv`
- `links.csv`
- `demands.csv`
- `setting.csv`

## Freeze protocol

Do not manually edit, filter, reorder, or regenerate the source files.

Run:

```bash
python scripts/freeze_reference_instance.py \
  --source /path/to/exact/nicolas/toy/data \
  --output data/reference/reconstruction/8x50
```

The freezer has two hard guards:

- exactly **8** rows with `node_type=yard`;
- exactly **50** commodity rows in `demands.csv`.

It copies the four files byte-for-byte and creates `manifest.json` with
SHA-256 hashes.

If either count fails, the command stops. In particular, **do not create a
synthetic replacement** and call it the Nicolas reference instance.

## R1 acceptance criteria

R1 is complete only when:

1. the exact source directory has been identified;
2. the freezer succeeds with 8 yards / 50 commodities;
3. the four input hashes are recorded;
4. Greedy, VLNS and MIP can all load the frozen directory;
5. their outputs, objective, feasibility, runtime and solver parameters are
   captured by `scripts/run_reference_reconstruction.py`.

Until these conditions are met, no numerical claim about reproducing the
Nicolas reference result should be made.
