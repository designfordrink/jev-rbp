#!/usr/bin/env bash
# Local equivalent of the repository's required CI checks.
set -euo pipefail
python -m pytest -q
python -m ruff check .
