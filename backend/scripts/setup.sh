#!/usr/bin/env bash
# Git Bash setup: Poetry + Python 3.12 (avoid Windows Store python stub)
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON312="$(py -3.12 -c 'import sys; print(sys.executable)' 2>/dev/null || true)"
if [[ -z "$PYTHON312" ]]; then
  echo "Python 3.12 not found. Install with:"
  echo "  winget install Python.Python.3.12"
  exit 1
fi

POETRY_DIR="$APPDATA/Python/Scripts"
export PATH="$POETRY_DIR:$(dirname "$PYTHON312"):$PATH"

if ! command -v poetry >/dev/null 2>&1; then
  echo "Poetry not found. Install with:"
  echo "  py -3.12 -m pip install poetry"
  exit 1
fi

echo "Using Python: $PYTHON312"
poetry config virtualenvs.in-project true --local
poetry env use "$PYTHON312"
poetry lock --no-update 2>/dev/null || poetry lock
poetry install

echo ""
echo "Done. Run:"
echo "  source .venv/Scripts/activate"
echo "  poetry run pytest"
echo "  poetry run uvicorn src.main:app --reload"
