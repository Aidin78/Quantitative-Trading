# Backend

Python backend for the Quantitative Trading Signal Platform.

## Setup (Windows)

**Poetry** must use **Python 3.12** (not the Windows Store stub, not 3.14 — `asyncpg` fails on 3.14).

```powershell
# One-time: install Python 3.12 if missing
winget install Python.Python.3.12

# From backend/
.\scripts\setup.ps1
```

Git Bash:

```bash
bash scripts/setup.sh
```

Manual:

```bash
py -3.12 -m pip install poetry   # if poetry missing
export PATH="$APPDATA/Python/Scripts:$PATH"
poetry env use "$(py -3.12 -c 'import sys; print(sys.executable)')"
poetry install
```

## Setup (generic)

```bash
cd backend
poetry install
cp ../.env.example ../.env
poetry run pytest
poetry run uvicorn src.main:app --reload
```
