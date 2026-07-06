# Backend

Python backend for the Quantitative Trading Signal Platform.

## Setup

```bash
cd backend
poetry install
cp ../.env.example ../.env
poetry run pytest
poetry run uvicorn src.main:app --reload
```

Config files live in `../config/`.
