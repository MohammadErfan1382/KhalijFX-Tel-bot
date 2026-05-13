.PHONY: help up down logs shell test lint format migrate revision

help:
	@echo "دستورات موجود:"
	@echo "  make up        — راه‌اندازی همه سرویس‌ها"
	@echo "  make down      — خاموش کردن سرویس‌ها"
	@echo "  make logs      — نمایش لاگ‌های ربات"
	@echo "  make shell     — ورود به shell ربات"
	@echo "  make test      — اجرای تست‌ها"
	@echo "  make lint      — بررسی کد"
	@echo "  make format    — فرمت کردن کد"
	@echo "  make migrate   — اعمال migration ها"
	@echo "  make revision  — ساخت migration جدید"
	@echo "  make flower    — باز کردن Celery monitor"

up:
	docker compose up -d
	@echo "✅ سرویس‌ها راه‌اندازی شدند"

up-dev:
	docker compose --profile dev up -d

down:
	docker compose down

logs:
	docker compose logs -f bot

logs-worker:
	docker compose logs -f worker

shell:
	docker compose exec bot bash

test:
	poetry run pytest tests/ -v --cov=app --cov-report=term-missing

test-unit:
	poetry run pytest tests/unit/ -v

test-integration:
	poetry run pytest tests/integration/ -v

lint:
	poetry run ruff check app/ tests/
	poetry run mypy app/

format:
	poetry run ruff format app/ tests/
	poetry run ruff check --fix app/ tests/

migrate:
	docker compose exec bot alembic upgrade head

revision:
	@read -p "نام migration: " name; \
	docker compose exec bot alembic revision --autogenerate -m "$$name"

flower:
	@echo "Celery Flower: http://localhost:5555"
	open http://localhost:5555

# نصب اولیه پروژه
install:
	pip install poetry==1.8.3
	poetry install
	cp .env.example .env
	@echo "⚠️  فایل .env را تنظیم کنید و سپس 'make up' را اجرا کنید"
