# راه‌اندازی روی GitHub Codespaces

## ۱. تنظیم Secrets (یک بار، قبل از ساخت Codespace)

به آدرس زیر برو:
```
https://github.com/YOUR_USERNAME/exchange-bot/settings/secrets/codespaces
```

سه secret زیر رو اضافه کن:

| نام Secret | مقدار |
|-----------|-------|
| `BOT_TOKEN` | توکن ربات از @BotFather |
| `ENCRYPTION_KEY` | دقیقاً ۳۲ کاراکتر (مثال: `abcdef1234567890abcdef1234567890`) |
| `ADMIN_USER_IDS` | آیدی عددی تلگرام خودت (از @userinfobot بگیر) |

---

## ۲. ساخت Codespace

روی دکمه سبز **Code** در GitHub کلیک کن:

```
Code > Codespaces > Create codespace on main
```

ساخته شدن حدود **۳-۵ دقیقه** طول میکشه — همه چیز خودکار نصب میشه.

---

## ۳. اجرای ربات

وقتی Codespace باز شد، در ترمینال:

```bash
# حالت ساده (فقط ربات)
poetry run python -m app.main

# حالت کامل (ربات + celery + beat در tmux)
bash .devcontainer/run-dev.sh
```

---

## ۴. بررسی سلامت سرویس‌ها

```bash
# دیتابیس
psql -h localhost -U exchange_user -d exchange_db -c "SELECT version();"

# Redis
redis-cli ping   # باید PONG برگرده

# migrations وضعیت
poetry run alembic current
```

---

## ۵. دستورات مفید در Codespace

```bash
# تست‌ها
poetry run pytest tests/ -v

# migration جدید
poetry run alembic revision --autogenerate -m "add_new_field"

# اعمال migration
poetry run alembic upgrade head

# لاگ‌های Celery در background
celery -A app.tasks.celery_app worker --loglevel=debug &
```

---

## نکات مهم

**polling vs webhook:**
در Codespace حتماً از **polling** استفاده کن (پیش‌فرض).
`WEBHOOK_URL` رو خالی بذار در `.env`.

**پورت‌های forward شده:**
- `5432` → PostgreSQL
- `6379` → Redis
- `5555` → Celery Flower (اگه اجرا کنی)

**محدودیت رایگان Codespace:**
- ۶۰ ساعت در ماه برای plan رایگان
- وقتی کار نداری، Codespace رو **Stop** کن (نه Delete)

---

## مشکلات رایج

**خطای `BOT_TOKEN not set`:**
```bash
# بررسی کن secret لود شده
echo $BOT_TOKEN
# اگه خالی بود، .env رو دستی ویرایش کن
nano .env
```

**دیتابیس connect نمیشه:**
```bash
sudo service postgresql status
sudo service postgresql start
```

**Redis connect نمیشه:**
```bash
sudo service redis-server status
sudo service redis-server start
```
