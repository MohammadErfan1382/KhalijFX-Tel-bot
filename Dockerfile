# ── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main --no-root --no-interaction


# ── Stage 2: Production ─────────────────────────────────────────────────────
FROM python:3.11-slim AS production

# psycopg2 و asyncpg نیاز به libpq دارن
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# کپی venv از builder
COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# کپی source code
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# کاربر non-root برای امنیت
RUN groupadd -r botuser && useradd -r -g botuser botuser
USER botuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import asyncio; from app.core.database import check_db_connection; asyncio.run(check_db_connection())"

CMD ["python", "-m", "app.main"]
