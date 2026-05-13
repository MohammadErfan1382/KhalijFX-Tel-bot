from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "exchange_bot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.notifications"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tehran",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,          # task فقط بعد از موفقیت ACK میشه
    worker_prefetch_multiplier=1, # یک task در هر لحظه برای reliability
    beat_schedule={
        # هر ۶۰ ثانیه نرخ رو pre-warm میکنیم تا کش خالی نشه
        "refresh-rates": {
            "task": "app.tasks.notifications.refresh_rates_cache",
            "schedule": 55.0,  # کمی کمتر از TTL
        },
    },
)
