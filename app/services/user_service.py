from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.audit_log import AuditAction
from app.models.user import KYCStatus, User
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.audit_repo = AuditRepository(session)

    async def submit_kyc(
        self,
        user: User,
        full_name: str,
        national_id: str,
        phone_number: str,
        document_file_id: str,
    ) -> User:
        if user.kyc_status == KYCStatus.VERIFIED:
            raise ValueError("کاربر قبلاً تایید شده است")
        if user.kyc_status == KYCStatus.SUBMITTED:
            raise ValueError("درخواست احراز هویت شما در حال بررسی است")

        user = await self.user_repo.update_kyc_submitted(
            user=user,
            full_name=full_name,
            national_id=national_id,
            phone_number=phone_number,
            document_file_id=document_file_id,
        )

        await self.audit_repo.log(
            user_id=user.id,
            action=AuditAction.KYC_SUBMITTED,
            metadata={"national_id_last4": national_id[-4:]},
        )

        logger.info("kyc_submitted", telegram_id=user.telegram_id)
        return user

    async def approve_kyc(self, user: User, admin_telegram_id: int) -> User:
        if user.kyc_status == KYCStatus.VERIFIED:
            raise ValueError("کاربر قبلاً تایید شده است")

        user = await self.user_repo.approve_kyc(user, admin_telegram_id)

        await self.audit_repo.log(
            user_id=user.id,
            action=AuditAction.KYC_APPROVED,
            performed_by=admin_telegram_id,
        )

        logger.info(
            "kyc_approved",
            telegram_id=user.telegram_id,
            by_admin=admin_telegram_id,
        )
        return user

    async def reject_kyc(
        self, user: User, admin_telegram_id: int, reason: str
    ) -> User:
        user = await self.user_repo.reject_kyc(user, admin_telegram_id, reason)

        await self.audit_repo.log(
            user_id=user.id,
            action=AuditAction.KYC_REJECTED,
            performed_by=admin_telegram_id,
            metadata={"reason": reason},
        )

        logger.info(
            "kyc_rejected",
            telegram_id=user.telegram_id,
            by_admin=admin_telegram_id,
        )
        return user

    async def list_pending_kyc(self) -> list[User]:
        return await self.user_repo.list_pending_kyc()

    async def block_user(self, user: User, admin_telegram_id: int) -> User:
        user = await self.user_repo.set_blocked(user, True)
        await self.audit_repo.log(
            user_id=user.id,
            action=AuditAction.ADMIN_USER_BLOCKED,
            performed_by=admin_telegram_id,
        )
        return user

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in settings.admin_user_ids
