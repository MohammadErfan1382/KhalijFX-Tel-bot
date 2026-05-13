#!/bin/bash
# این فایل رو به bashrc اضافه کن تا هر بار terminal باز شد نمایش داده بشه
# post-create.sh این کار رو میکنه

cat << 'BANNER'

  ╔══════════════════════════════════════════╗
  ║       Exchange Bot — Codespace           ║
  ╠══════════════════════════════════════════╣
  ║  راه‌اندازی سریع:                        ║
  ║                                          ║
  ║  1) DB + Redis را بالا بیار:             ║
  ║     docker compose \                     ║
  ║       -f docker-compose.codespaces.yml \ ║
  ║       up -d db redis                     ║
  ║                                          ║
  ║  2) ربات را اجرا کن:                    ║
  ║     poetry run python -m app.main        ║
  ║                                          ║
  ║  3) تست:                                ║
  ║     poetry run pytest tests/ -v          ║
  ╚══════════════════════════════════════════╝

BANNER

# بررسی وضعیت secrets
if grep -q "BOT_TOKEN=your_bot_token_here" .env 2>/dev/null; then
  echo "  ⚠️  BOT_TOKEN تنظیم نشده — Codespaces Secrets را بررسی کن"
  echo ""
fi
