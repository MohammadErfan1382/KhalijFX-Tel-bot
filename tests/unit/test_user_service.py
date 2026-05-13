from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import KYCStatus, User
from app.services.user_service import UserService
from tests.conftest import make_user


class TestUserServiceKYC:

    async def test_submit_kyc_success(self, session: AsyncSession, pending_user: User):
        service = UserService(session)
        updated = await service.submit_kyc(
            user=pending_user,
            full_name="علی احمدی",
            national_id="1234567890",
            phone_number="09121234567",
            document_file_id="file_abc123",
        )
        assert updated.kyc_status == KYCStatus.SUBMITTED
        assert updated.full_name == "علی احمدی"
        assert updated.national_id == "1234567890"
        assert updated.kyc_submitted_at is not None

    async def test_submit_kyc_already_verified_raises(
        self, session: AsyncSession, verified_user: User
    ):
        service = UserService(session)
        with pytest.raises(ValueError, match="قبلاً تایید شده"):
            await service.submit_kyc(
                user=verified_user,
                full_name="X",
                national_id="1234567890",
                phone_number="09121234567",
                document_file_id="file_xyz",
            )

    async def test_submit_kyc_already_submitted_raises(
        self, session: AsyncSession, submitted_user: User
    ):
        service = UserService(session)
        with pytest.raises(ValueError, match="در حال بررسی"):
            await service.submit_kyc(
                user=submitted_user,
                full_name="X",
                national_id="0000000000",
                phone_number="09120000000",
                document_file_id="file_000",
            )

    async def test_approve_kyc(self, session: AsyncSession, submitted_user: User):
        service = UserService(session)
        updated = await service.approve_kyc(submitted_user, admin_telegram_id=999)
        assert updated.kyc_status == KYCStatus.VERIFIED
        assert updated.kyc_reviewed_by == 999
        assert updated.kyc_reviewed_at is not None

    async def test_reject_kyc(self, session: AsyncSession, submitted_user: User):
        service = UserService(session)
        updated = await service.reject_kyc(
            submitted_user, admin_telegram_id=999, reason="مدارک ناخوانا"
        )
        assert updated.kyc_status == KYCStatus.REJECTED
        assert updated.kyc_reject_reason == "مدارک ناخوانا"
        assert updated.kyc_reviewed_by == 999

    async def test_approve_already_verified_raises(
        self, session: AsyncSession, verified_user: User
    ):
        service = UserService(session)
        with pytest.raises(ValueError, match="قبلاً تایید شده"):
            await service.approve_kyc(verified_user, admin_telegram_id=999)

    async def test_list_pending_kyc_returns_submitted_users(
        self, session: AsyncSession
    ):
        # چند کاربر با وضعیت‌های مختلف
        await make_user(session, telegram_id=1, kyc_status=KYCStatus.PENDING)
        await make_user(session, telegram_id=2, kyc_status=KYCStatus.SUBMITTED)
        await make_user(session, telegram_id=3, kyc_status=KYCStatus.SUBMITTED)
        await make_user(session, telegram_id=4, kyc_status=KYCStatus.VERIFIED)

        service = UserService(session)
        pending = await service.list_pending_kyc()

        assert len(pending) == 2
        for u in pending:
            assert u.kyc_status == KYCStatus.SUBMITTED

    async def test_block_user(self, session: AsyncSession, pending_user: User):
        service = UserService(session)
        blocked = await service.block_user(pending_user, admin_telegram_id=999)
        assert blocked.is_blocked is True

    async def test_is_admin_with_valid_id(self, session: AsyncSession):
        service = UserService(session)
        # admin_user_ids در test env خالیه، پس False برمیگرده
        assert service.is_admin(123456) is False
