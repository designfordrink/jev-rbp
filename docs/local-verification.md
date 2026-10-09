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

## Run automatically before every commit

Install the development dependencies and activate the repository hook once per local clone:

```bash
python -m pip install -e ".[dev]"
pre-commit install
```

The hook runs `bash scripts/verify.sh` before each commit, so test failures and Ruff errors such as line-length violations are caught before the commit is created. To run the hook manually at any time, use `pre-commit run --all-files`.

Git hooks are local to each clone; every developer must run `pre-commit install` once. GitHub Actions remains the authoritative check on the pushed commit.

A green local run reduces avoidable CI failures but does not replace CI: the remote runner checks the exact pushed commit in its own clean environment.
