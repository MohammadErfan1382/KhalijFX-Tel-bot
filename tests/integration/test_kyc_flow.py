from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import KYCStatus
from app.repositories.user_repo import UserRepository
from app.services.user_service import UserService
from tests.conftest import make_user


class TestKYCIntegrationFlow:
    """
    تست end-to-end فلوی کامل KYC:
    ثبت → ارسال مدارک → تایید/رد ادمین → نتیجه
    """

    async def test_full_kyc_approval_flow(self, session: AsyncSession):
        # ۱. کاربر جدید ثبت میشه
        repo = UserRepository(session)
        user = await repo.create(
            telegram_id=77777771,
            first_name="محمد",
            last_name="محمدی",
        )
        assert user.kyc_status == KYCStatus.PENDING

        # ۲. کاربر درخواست KYC میفرسته
        service = UserService(session)
        user = await service.submit_kyc(
            user=user,
            full_name="محمد محمدی",
            national_id="1111111111",
            phone_number="09111111111",
            document_file_id="file_test_001",
        )
        assert user.kyc_status == KYCStatus.SUBMITTED
        assert user.kyc_submitted_at is not None

        # ۳. ادمین لیست در انتظار رو میبینه
        pending_list = await service.list_pending_kyc()
        assert any(u.id == user.id for u in pending_list)

        # ۴. ادمین تایید میکنه
        user = await service.approve_kyc(user, admin_telegram_id=999999999)
        assert user.kyc_status == KYCStatus.VERIFIED
        assert user.kyc_reviewed_by == 999999999

        # ۵. دیگه در لیست pending نیست
        pending_list_after = await service.list_pending_kyc()
        assert not any(u.id == user.id for u in pending_list_after)

        # ۶. is_verified property
        assert user.is_verified is True

    async def test_full_kyc_rejection_flow(self, session: AsyncSession):
        repo = UserRepository(session)
        user = await repo.create(telegram_id=77777772, first_name="حسن")

        service = UserService(session)
        user = await service.submit_kyc(
            user=user,
            full_name="حسن حسنی",
            national_id="2222222222",
            phone_number="09122222222",
            document_file_id="file_test_002",
        )
        assert user.kyc_status == KYCStatus.SUBMITTED

        # رد شدن با دلیل
        user = await service.reject_kyc(
            user, admin_telegram_id=999999999, reason="تصویر ناخوانا"
        )
        assert user.kyc_status == KYCStatus.REJECTED
        assert user.kyc_reject_reason == "تصویر ناخوانا"

        # بعد از رد، کاربر میتونه دوباره ارسال کنه
        user = await service.submit_kyc(
            user=user,
            full_name="حسن حسنی",
            national_id="2222222222",
            phone_number="09122222222",
            document_file_id="file_test_002_new",
        )
        assert user.kyc_status == KYCStatus.SUBMITTED
        assert user.document_file_id == "file_test_002_new"

    async def test_kyc_and_order_full_flow(self, session: AsyncSession):
        """تست کامل: KYC تایید شده → ثبت سفارش"""
        from decimal import Decimal
        from app.services.order_service import OrderService
        from app.models.order import OrderType, OrderStatus

        # ایجاد کاربر و تایید KYC
        repo = UserRepository(session)
        user = await repo.create(telegram_id=77777773, first_name="فاطمه")

        user_svc = UserService(session)
        user = await user_svc.submit_kyc(
            user=user,
            full_name="فاطمه فاطمی",
            national_id="3333333333",
            phone_number="09133333333",
            document_file_id="file_test_003",
        )
        user = await user_svc.approve_kyc(user, admin_telegram_id=999999999)
        assert user.is_verified

        # ثبت سفارش
        order_svc = OrderService(session)
        order = await order_svc.create_order(
            user=user,
            order_type=OrderType.BUY,
            currency_from="IRR",
            currency_to="USD",
            amount=Decimal("200"),
            rate=Decimal("58000"),
        )
        assert order.status == OrderStatus.PENDING
        assert order.total_amount == Decimal("200") * Decimal("58000")

        # لیست سفارش‌ها
        orders = await order_svc.get_user_orders(user)
        assert len(orders) == 1
        assert orders[0].id == order.id

        # لغو سفارش
        cancelled = await order_svc.cancel_order(user, order.reference_code)
        assert cancelled.status == OrderStatus.CANCELLED
