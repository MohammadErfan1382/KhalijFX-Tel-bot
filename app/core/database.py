from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class برای تمام مدل‌ها"""
    pass


# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,       # SQL log در dev
    pool_size=10,                           # connection های همیشه باز
    max_overflow=20,                        # connection های اضافی در پیک
    pool_pre_ping=True,                     # بررسی اتصال قبل از استفاده
    pool_recycle=3600,                      # بازسازی connection بعد از 1 ساعت
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,   # جلوگیری از lazy load بعد از commit
    autoflush=False,
    autocommit=False,
)


# ── Dependency / Context Manager ──────────────────────────────────────────────
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager برای دریافت session.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(...)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency برای aiogram middleware و جاهایی که generator لازمه.
    """
    async with get_db_session() as session:
        yield session


async def check_db_connection() -> bool:
    """Health check برای دیتابیس"""
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        return False


async def close_db() -> None:
    """بستن engine - در shutdown"""
    await engine.dispose()
    logger.info("database_engine_disposed")
