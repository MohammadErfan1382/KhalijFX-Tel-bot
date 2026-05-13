# 🏦 Exchange Bot — ربات تلگرام صرافی

ربات تلگرام حرفه‌ای برای مدیریت صرافی ارز، با قابلیت احراز هویت، ثبت سفارش، و پنل ادمین.

---

## معماری

```
Telegram API
     │
   aiogram v3 (async bot framework)
     │
   Middlewares (Auth, RateLimit, DB Session)
     │
   Handlers (public / kyc / verified / admin)
     │
   Services (UserService, OrderService, RateService)
     │
   Repositories (UserRepo, OrderRepo, AuditRepo)
     │
   PostgreSQL ←→ Redis (Cache + FSM + Queue)
                    │
                 Celery Workers (Notifications)
```

---

## پیش‌نیازها

- Docker & Docker Compose
- Python 3.11+ (برای توسعه محلی)
- توکن ربات تلگرام از [@BotFather](https://t.me/BotFather)

---

## راه‌اندازی سریع

```bash
# ۱. کلون
git clone https://github.com/yourorg/exchange-bot
cd exchange-bot

# ۲. نصب
make install

# ۳. تنظیم .env
nano .env   # BOT_TOKEN, ADMIN_USER_IDS, و بقیه موارد را پر کنید

# ۴. راه‌اندازی
make up

# ۵. مشاهده لاگ
make logs
```

---

## متغیرهای محیطی مهم

| متغیر | توضیح | اجباری |
|-------|-------|--------|
| `BOT_TOKEN` | توکن ربات از BotFather | ✅ |
| `POSTGRES_PASSWORD` | رمز دیتابیس | ✅ |
| `ENCRYPTION_KEY` | کلید رمزگذاری (32 کاراکتر) | ✅ |
| `ADMIN_USER_IDS` | آیدی تلگرام ادمین‌ها (کاما جدا) | ✅ |
| `WEBHOOK_URL` | آدرس webhook (در production) | در production |

---

## دستورات ادمین

| دستور | عملکرد |
|-------|--------|
| `/admin` | پنل مدیریت |
| `/pending_kyc` | لیست درخواست‌های احراز هویت |
| `/set_rate` | تنظیم نرخ داخلی |

---

## ساختار پروژه

```
exchange-bot/
├── app/
│   ├── bot/
│   │   ├── handlers/       # public, kyc, verified, admin
│   │   ├── middlewares/    # db, auth, rate_limit
│   │   ├── keyboards/      # inline و reply keyboards
│   │   └── states.py       # FSM states
│   ├── services/           # Business logic
│   ├── models/             # SQLAlchemy ORM
│   ├── repositories/       # Data access layer
│   ├── tasks/              # Celery tasks
│   └── core/               # config, database, redis, logging
├── migrations/             # Alembic
├── tests/
│   ├── unit/
│   └── integration/
├── docker-compose.yml
├── Dockerfile
└── Makefile
```

---

## توسعه

```bash
# اجرای تست‌ها
make test

# lint
make lint

# فرمت کد
make format

# ساخت migration جدید
make revision

# مانیتور Celery
make flower   # http://localhost:5555
```

---

## فلوی KYC

```
کاربر جدید (PENDING)
    │
    ▼
درخواست احراز هویت → ارسال مدارک (SUBMITTED)
    │
    ▼
بررسی ادمین
    ├── تایید → VERIFIED (دسترسی به ثبت سفارش + نرخ داخلی)
    └── رد    → REJECTED (امکان ارسال مجدد)
```

---

## مقیاس‌پذیری

- **الان:** Docker Compose، یک سرور
- **مرحله بعد:** چند instance از bot + Redis Sentinel
- **بزرگ‌تر:** Kubernetes، PostgreSQL replication، Redis Cluster
