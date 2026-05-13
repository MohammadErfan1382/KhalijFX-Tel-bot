from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.user import KYCStatus, User, UserRole
from app.models.order import Order, OrderType, OrderStatus


# ── Event loop ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── In-memory SQLite برای تست ─────────────────────────────────────────────────
@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()


# ── Factory helpers ───────────────────────────────────────────────────────────
async def make_user(
    session: AsyncSession,
    telegram_id: int = 100000001,
    kyc_status: KYCStatus = KYCStatus.PENDING,
    role: UserRole = UserRole.USER,
    **kwargs: Any,
) -> User:
    from app.repositories.user_repo import UserRepository
    repo = UserRepository(session)
    user = await repo.create(
        telegram_id=telegram_id,
        first_name=kwargs.get("first_name", "Ali"),
        last_name=kwargs.get("last_name", "Ahmadi"),
        username=kwargs.get("username", "ali_ahmadi"),
    )
    user.kyc_status = kyc_status
    user.role = role
    if kyc_status == KYCStatus.VERIFIED:
        user.full_name = "علی احمدی"
        user.national_id = "1234567890"
        user.phone_number = "09121234567"
        user.document_file_id = "fake_file_id_123"
    await session.flush()
    return user


@pytest_asyncio.fixture
async def pending_user(session: AsyncSession) -> User:
    return await make_user(session, telegram_id=100000001, kyc_status=KYCStatus.PENDING)


@pytest_asyncio.fixture
async def submitted_user(session: AsyncSession) -> User:
    u = await make_user(session, telegram_id=100000002, kyc_status=KYCStatus.SUBMITTED)
    u.full_name = "رضا رضایی"
    u.national_id = "9876543210"
    u.phone_number = "09129876543"
    u.document_file_id = "fake_doc_456"
    await session.flush()
    return u


@pytest_asyncio.fixture
async def verified_user(session: AsyncSession) -> User:
    return await make_user(session, telegram_id=100000003, kyc_status=KYCStatus.VERIFIED)


@pytest_asyncio.fixture
async def admin_user(session: AsyncSession) -> User:
    return await make_user(
        session,
        telegram_id=999999999,
        kyc_status=KYCStatus.VERIFIED,
        role=UserRole.ADMIN,
    )


# ── Mock Redis ────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_cache_redis():
    """Redis mock برای تست‌هایی که به cache نیاز دارن"""
    with patch("app.services.rate_service.cache_redis") as mock:
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        yield mock


# ── Mock Celery ───────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def mock_celery_tasks():
    """همه Celery task ها رو در تست mock میکنیم"""
    with (
        patch("app.tasks.notifications.notify_admins_new_kyc") as mock_kyc,
        patch("app.tasks.notifications.notify_user_kyc_result") as mock_result,
    ):
        mock_kyc.delay = MagicMock()
        mock_result.delay = MagicMock()
        yield {"kyc": mock_kyc, "result": mock_result}
