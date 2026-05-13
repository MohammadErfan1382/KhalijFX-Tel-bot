# ── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# نصب dependencies سیستمی برای build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# نصب مستقیم با pip — بدون virtualenv
# --prefix باعث میشه همه چیز در یک پوشه جمع بشه
# تا در stage بعدی فقط همونو کپی کنیم
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production ─────────────────────────────────────────────────────
FROM python:3.11-slim AS production

# فقط runtime dependency — نه gcc و build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# کپی packages نصب‌شده از builder
COPY --from=builder /install /usr/local

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
