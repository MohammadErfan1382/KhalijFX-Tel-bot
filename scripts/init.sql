-- این فایل فقط یه بار در اولین راه‌اندازی اجرا میشه

-- Extension برای UUID generation در سطح دیتابیس
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extension برای full-text search فارسی (اگه نیاز شد)
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- تنظیم timezone
SET timezone = 'Asia/Tehran';
