FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry==1.8.4

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY src ./src
COPY scripts ./scripts
COPY README.md ./

RUN poetry install --no-interaction --no-ansi --only-root

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
