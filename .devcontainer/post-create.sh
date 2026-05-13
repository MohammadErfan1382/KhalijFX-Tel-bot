#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Exchange Bot — Codespace Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "[1/4] نصب Poetry و dependencies..."
pip install --quiet poetry==1.8.3
poetry config virtualenvs.in-project true
poetry install --no-interaction

echo "[2/4] ساخت فایل .env..."
if [ ! -f .env ]; then
  cp .env.example .env
  [ -n "$BOT_TOKEN" ]         && sed -i "s|BOT_TOKEN=.*|BOT_TOKEN=$BOT_TOKEN|" .env
  [ -n "$ADMIN_USER_IDS" ]    && sed -i "s|ADMIN_USER_IDS=.*|ADMIN_USER_IDS=$ADMIN_USER_IDS|" .env
  [ -n "$ENCRYPTION_KEY" ]    && sed -i "s|ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$ENCRYPTION_KEY|" .env
  [ -n "$POSTGRES_PASSWORD" ] && sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env
  sed -i "s|WEBHOOK_URL=.*|WEBHOOK_URL=|" .env
  sed -i "s|APP_ENV=.*|APP_ENV=development|" .env
  echo "  ✓ .env ساخته شد"
else
  echo "  ✓ .env از قبل موجود است"
fi

echo "[3/4] تنظیم pre-commit hook..."
cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/bash
poetry run ruff check app/ tests/ --quiet
poetry run ruff format --check app/ tests/ --quiet
HOOK
chmod +x .git/hooks/pre-commit
echo "  ✓ pre-commit hook فعال شد"

echo "[4/4] آماده!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  دستورات:"
echo "    docker compose -f docker-compose.codespaces.yml up -d db redis"
echo "    poetry run python -m app.main"
echo "    poetry run pytest tests/ -v"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if grep -q "BOT_TOKEN=your_bot_token_here" .env 2>/dev/null; then
  echo ""
  echo "  ⚠️  BOT_TOKEN هنوز تنظیم نشده!"
  echo "     Settings → Secrets and variables → Codespaces"
  echo "     Secret های لازم:"
  echo "       BOT_TOKEN, ADMIN_USER_IDS, ENCRYPTION_KEY, POSTGRES_PASSWORD"
fi
