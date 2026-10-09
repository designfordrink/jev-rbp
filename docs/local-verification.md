# Local verification before pushing

Run the same two checks required by GitHub Actions before opening or updating a pull request:

```bash
bash scripts/verify.sh
```

The script stops on the first failure and runs:

1. `python -m pytest -q`
2. `python -m ruff check .`

Install the project and development tools first:

```bash
python -m pip install -e ".[dev]"
```

## Optional: run before every commit

To run checks automatically before each local commit, install the `pre-commit` package and configure a Git hook to call `bash scripts/verify.sh`. This repository does not silently install Git hooks, because doing so changes local Git behavior. GitHub Actions remains the authoritative required check.

A green local run reduces avoidable CI failures but does not replace CI: the remote runner checks the exact pushed commit in its own clean environment.
