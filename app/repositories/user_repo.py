from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import KYCStatus, User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        telegram_id: int,
        first_name: str,
        last_name: str | None = None,
        username: str | None = None,
        language_code: str | None = None,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
            language_code=language_code,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_kyc_submitted(
        self,
        user: User,
        full_name: str,
        national_id: str,
        phone_number: str,
        document_file_id: str,
    ) -> User:
        user.full_name = full_name
        user.national_id = national_id
        user.phone_number = phone_number
        user.document_file_id = document_file_id
        user.kyc_status = KYCStatus.SUBMITTED
        user.kyc_submitted_at = datetime.now(timezone.utc)
        await self.session.flush()
        return user

    async def approve_kyc(self, user: User, admin_telegram_id: int) -> User:
        user.kyc_status = KYCStatus.VERIFIED
        user.kyc_reviewed_at = datetime.now(timezone.utc)
        user.kyc_reviewed_by = admin_telegram_id
        user.kyc_reject_reason = None
        await self.session.flush()
        return user

    async def reject_kyc(
        self, user: User, admin_telegram_id: int, reason: str
    ) -> User:
        user.kyc_status = KYCStatus.REJECTED
        user.kyc_reviewed_at = datetime.now(timezone.utc)
        user.kyc_reviewed_by = admin_telegram_id
        user.kyc_reject_reason = reason
        await self.session.flush()
        return user

    async def set_blocked(self, user: User, blocked: bool) -> User:
        user.is_blocked = blocked
        await self.session.flush()
        return user

    async def list_pending_kyc(self) -> list[User]:
        result = await self.session.execute(
            select(User)
            .where(User.kyc_status == KYCStatus.SUBMITTED)
            .order_by(User.kyc_submitted_at)
        )
        return list(result.scalars().all())
