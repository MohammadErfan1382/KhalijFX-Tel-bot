from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import OrderStatus, OrderType
from app.models.user import KYCStatus
from app.repositories.order_repo import OrderRepository
from app.repositories.user_repo import UserRepository
from tests.conftest import make_user


class TestUserRepository:

    async def test_create_user(self, session: AsyncSession):
        repo = UserRepository(session)
        user = await repo.create(
            telegram_id=12345678,
            first_name="تست",
            last_name="کاربر",
            username="test_user",
        )
        assert user.id is not None
        assert user.telegram_id == 12345678
        assert user.kyc_status == KYCStatus.PENDING

    async def test_get_by_telegram_id_existing(self, session: AsyncSession):
        repo = UserRepository(session)
        created = await repo.create(telegram_id=11111111, first_name="علی")
        found = await repo.get_by_telegram_id(11111111)
        assert found is not None
        assert found.id == created.id

    async def test_get_by_telegram_id_nonexistent(self, session: AsyncSession):
        repo = UserRepository(session)
        result = await repo.get_by_telegram_id(99999999999)
        assert result is None

    async def test_update_kyc_submitted(self, session: AsyncSession):
        repo = UserRepository(session)
        user = await repo.create(telegram_id=22222222, first_name="رضا")
        updated = await repo.update_kyc_submitted(
            user=user,
            full_name="رضا رضایی",
            national_id="1234567890",
            phone_number="09121234567",
            document_file_id="file_abc",
        )
        assert updated.kyc_status == KYCStatus.SUBMITTED
        assert updated.kyc_submitted_at is not None

    async def test_approve_kyc(self, session: AsyncSession):
        u = await make_user(session, telegram_id=33333333, kyc_status=KYCStatus.SUBMITTED)
        repo = UserRepository(session)
        approved = await repo.approve_kyc(u, admin_telegram_id=999)
        assert approved.kyc_status == KYCStatus.VERIFIED
        assert approved.kyc_reviewed_by == 999

    async def test_reject_kyc(self, session: AsyncSession):
        u = await make_user(session, telegram_id=44444444, kyc_status=KYCStatus.SUBMITTED)
        repo = UserRepository(session)
        rejected = await repo.reject_kyc(u, admin_telegram_id=999, reason="ناخوانا")
        assert rejected.kyc_status == KYCStatus.REJECTED
        assert rejected.kyc_reject_reason == "ناخوانا"

    async def test_list_pending_kyc(self, session: AsyncSession):
        await make_user(session, telegram_id=55555551, kyc_status=KYCStatus.PENDING)
        await make_user(session, telegram_id=55555552, kyc_status=KYCStatus.SUBMITTED)
        await make_user(session, telegram_id=55555553, kyc_status=KYCStatus.SUBMITTED)
        await make_user(session, telegram_id=55555554, kyc_status=KYCStatus.VERIFIED)

        repo = UserRepository(session)
        pending = await repo.list_pending_kyc()
        assert len(pending) == 2


class TestOrderRepository:

    async def test_create_order(self, session: AsyncSession, verified_user):
        repo = OrderRepository(session)
        order = await repo.create(
            user_id=verified_user.id,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("500"),
            rate_at_order=Decimal("58000"),
            total_amount=Decimal("29000000"),
        )
        assert order.reference_code.startswith("EX-")
        assert order.status == OrderStatus.PENDING

    async def test_get_by_reference(self, session: AsyncSession, verified_user):
        repo = OrderRepository(session)
        order = await repo.create(
            user_id=verified_user.id,
            order_type=OrderType.SELL,
            currency_from="USD",
            currency_to="IRR",
            amount=Decimal("10"),
            rate_at_order=Decimal("58000"),
            total_amount=Decimal("580000"),
        )
        found = await repo.get_by_reference(order.reference_code)
        assert found is not None
        assert found.id == order.id

    async def test_count_today_orders(self, session: AsyncSession, verified_user):
        repo = OrderRepository(session)
        for i in range(3):
            await repo.create(
                user_id=verified_user.id,
                order_type=OrderType.BUY,
                currency_from="IRR",
                currency_to="USD",
                amount=Decimal(str(i + 1)),
                rate_at_order=Decimal("58000"),
                total_amount=Decimal("58000") * Decimal(str(i + 1)),
            )
        count = await repo.count_today_orders(verified_user.id)
        assert count == 3

    async def test_update_status(self, session: AsyncSession, verified_user):
        repo = OrderRepository(session)
        order = await repo.create(
            user_id=verified_user.id,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("100"),
            rate_at_order=Decimal("58000"),
            total_amount=Decimal("5800000"),
        )
        updated = await repo.update_status(order, OrderStatus.COMPLETED)
        assert updated.status == OrderStatus.COMPLETED
