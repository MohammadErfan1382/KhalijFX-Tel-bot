from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import OrderStatus, OrderType
from app.models.user import KYCStatus, User
from app.services.order_service import OrderService
from tests.conftest import make_user


class TestOrderService:

    async def test_create_order_success(self, session: AsyncSession, verified_user: User):
        service = OrderService(session)
        order = await service.create_order(
            user=verified_user,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("100"),
            rate=Decimal("58000"),
        )
        assert order.reference_code.startswith("EX-")
        assert order.amount == Decimal("100")
        assert order.total_amount == Decimal("5800000")
        assert order.status == OrderStatus.PENDING
        assert order.user_id == verified_user.id

    async def test_create_order_unverified_user_raises(
        self, session: AsyncSession, pending_user: User
    ):
        service = OrderService(session)
        with pytest.raises(PermissionError, match="احراز هویت"):
            await service.create_order(
                user=pending_user,
                order_type=OrderType.BUY,
                currency_from="IRR",
                currency_to="USD",
                amount=Decimal("100"),
                rate=Decimal("58000"),
            )

    async def test_create_order_zero_amount_raises(
        self, session: AsyncSession, verified_user: User
    ):
        service = OrderService(session)
        with pytest.raises(ValueError, match="بیشتر از صفر"):
            await service.create_order(
                user=verified_user,
                order_type=OrderType.BUY,
                currency_from="IRR",
                currency_to="USD",
                amount=Decimal("0"),
                rate=Decimal("58000"),
            )

    async def test_create_order_negative_amount_raises(
        self, session: AsyncSession, verified_user: User
    ):
        service = OrderService(session)
        with pytest.raises(ValueError):
            await service.create_order(
                user=verified_user,
                order_type=OrderType.SELL,
                currency_from="USD",
                currency_to="IRR",
                amount=Decimal("-50"),
                rate=Decimal("58000"),
            )

    async def test_reference_code_is_unique(
        self, session: AsyncSession, verified_user: User
    ):
        service = OrderService(session)
        orders = [
            await service.create_order(
                user=verified_user,
                order_type=OrderType.BUY,
                currency_from="IRR",
                currency_to="USD",
                amount=Decimal(str(i + 1)),
                rate=Decimal("58000"),
            )
            for i in range(5)
        ]
        refs = [o.reference_code for o in orders]
        assert len(set(refs)) == 5  # همه unique

    async def test_cancel_order_success(
        self, session: AsyncSession, verified_user: User
    ):
        service = OrderService(session)
        order = await service.create_order(
            user=verified_user,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("100"),
            rate=Decimal("58000"),
        )
        cancelled = await service.cancel_order(verified_user, order.reference_code)
        assert cancelled.status == OrderStatus.CANCELLED

    async def test_cancel_nonexistent_order_raises(
        self, session: AsyncSession, verified_user: User
    ):
        service = OrderService(session)
        with pytest.raises(ValueError, match="یافت نشد"):
            await service.cancel_order(verified_user, "EX-INVALID")

    async def test_cancel_other_user_order_raises(
        self, session: AsyncSession, verified_user: User
    ):
        other = await make_user(
            session, telegram_id=999888777, kyc_status=KYCStatus.VERIFIED
        )
        service = OrderService(session)
        order = await service.create_order(
            user=verified_user,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("100"),
            rate=Decimal("58000"),
        )
        with pytest.raises(PermissionError, match="متعلق به شما نیست"):
            await service.cancel_order(other, order.reference_code)

    async def test_get_user_orders(self, session: AsyncSession, verified_user: User):
        service = OrderService(session)
        for i in range(3):
            await service.create_order(
                user=verified_user,
                order_type=OrderType.BUY,
                currency_from="IRR",
                currency_to="USD",
                amount=Decimal(str(i + 1)),
                rate=Decimal("58000"),
            )
        orders = await service.get_user_orders(verified_user, limit=10)
        assert len(orders) == 3

    async def test_format_order_summary(
        self, session: AsyncSession, verified_user: User
    ):
        service = OrderService(session)
        order = await service.create_order(
            user=verified_user,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("100"),
            rate=Decimal("58000"),
        )
        summary = service.format_order_summary(order)
        assert order.reference_code in summary
        assert "خرید" in summary
        assert "58,000" in summary
