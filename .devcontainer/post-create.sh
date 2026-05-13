#!/bin/bash
set -e

echo ""
echo "========================================"
echo "  Exchange Bot — Codespace Setup"
echo "========================================"

# ── Poetry ────────────────────────────────────────────────
echo ""
echo "[1/5] نصب Poetry..."
pip install poetry==1.8.3 --quiet
poetry config virtualenvs.in-project true

# ── Dependencies ──────────────────────────────────────────
echo "[2/5] نصب dependencies..."
poetry install --no-interaction

# ── .env ──────────────────────────────────────────────────
echo "[3/5] ساخت فایل .env..."
if [ ! -f .env ]; then
    cp .env.example .env

    # مقادیر dev رو مستقیم inject میکنیم
    sed -i "s|POSTGRES_HOST=.*|POSTGRES_HOST=localhost|" .env
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=dev_password_123|" .env
    sed -i "s|REDIS_URL=.*|REDIS_URL=redis://localhost:6379/0|" .env
    sed -i "s|APP_ENV=.*|APP_ENV=development|" .env

    # اگه از Codespace Secrets خوندیم inject میکنیم
    if [ -n "$BOT_TOKEN" ]; then
        sed -i "s|BOT_TOKEN=.*|BOT_TOKEN=$BOT_TOKEN|" .env
    fi
    if [ -n "$ENCRYPTION_KEY" ]; then
        sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env
    fi
    if [ -n "$ADMIN_USER_IDS" ]; then
        sed -i "s|ADMIN_USER_IDS=.*|ADMIN_USER_IDS=$ADMIN_USER_IDS|" .env
    fi

    echo "     .env ساخته شد."
else
    echo "     .env از قبل وجود دارد."
fi

# ── PostgreSQL ────────────────────────────────────────────
echo "[4/5] آماده‌سازی دیتابیس..."
# منتظر میمونیم PostgreSQL بالا بیاد
for i in {1..15}; do
    if pg_isready -h localhost -U exchange_user -d exchange_db -q 2>/dev/null; then
        break
    fi
    echo "     منتظر PostgreSQL... ($i/15)"
    sleep 2
done

# اجرای migrations
poetry run alembic upgrade head
echo "     Migrations اعمال شدند."

# ── Redis ─────────────────────────────────────────────────
echo "[5/5] بررسی Redis..."
if redis-cli ping | grep -q PONG; then
    echo "     Redis آماده است."
else
    echo "     [WARN] Redis پاسخ نداد. دستی چک کن: redis-cli ping"
fi

echo ""
echo "========================================"
echo "  همه چیز آماده است!"
echo ""
echo "  برای شروع:"
echo "    poetry run python -m app.main"
echo ""
echo "  یا با tmux (چند پنجره):"
echo "    bash .devcontainer/run-dev.sh"
echo "========================================"
echo ""
