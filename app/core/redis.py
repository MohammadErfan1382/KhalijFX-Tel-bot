from __future__ import annotations

from redis.asyncio import Redis, ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Retry Policy ──────────────────────────────────────────────────────────────
_retry = Retry(ExponentialBackoff(cap=10, base=1), retries=3)


def _make_pool(url: str) -> ConnectionPool:
    return ConnectionPool.from_url(
        url,
        max_connections=50,
        decode_responses=True,
        retry=_retry,
        retry_on_error=[ConnectionError, TimeoutError],
        health_check_interval=30,
    )


# ── Connection Pools (یک بار ساخته میشن) ─────────────────────────────────────
_main_pool = _make_pool(settings.redis_url)
_fsm_pool = _make_pool(settings.redis_fsm_url)
_cache_pool = _make_pool(settings.redis_cache_url)


def get_redis() -> Redis:
    """Redis اصلی - برای rate limiting و داده‌های عمومی"""
    return Redis(connection_pool=_main_pool)


def get_fsm_redis() -> Redis:
    """Redis مخصوص FSM state های aiogram"""
    return Redis(connection_pool=_fsm_pool)


def get_cache_redis() -> Redis:
    """Redis مخصوص cache نرخ ارز"""
    return Redis(connection_pool=_cache_pool)


async def check_redis_connection() -> bool:
    """Health check"""
    try:
        r = get_redis()
        await r.ping()
        return True
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
        return False


async def close_redis() -> None:
    """بستن تمام pool ها در shutdown"""
    await _main_pool.aclose()
    await _fsm_pool.aclose()
    await _cache_pool.aclose()
    logger.info("redis_pools_closed")


# ── Singleton clients برای استفاده مستقیم ─────────────────────────────────────
redis_client = get_redis()
cache_redis = get_cache_redis()
