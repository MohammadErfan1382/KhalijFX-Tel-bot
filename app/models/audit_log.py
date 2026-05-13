from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    # KYC events
    KYC_SUBMITTED = "kyc_submitted"
    KYC_APPROVED = "kyc_approved"
    KYC_REJECTED = "kyc_rejected"

    # Order events
    ORDER_CREATED = "order_created"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_COMPLETED = "order_completed"

    # Admin events
    ADMIN_USER_BLOCKED = "admin_user_blocked"
    ADMIN_USER_UNBLOCKED = "admin_user_unblocked"
    ADMIN_ROLE_CHANGED = "admin_role_changed"

    # Auth events
    USER_REGISTERED = "user_registered"
    USER_BLOCKED = "user_blocked"


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """
    ردیابی تمام عملیات مهم.
    این جدول هیچوقت update یا delete نمیشه - فقط insert.
    """
    __tablename__ = "audit_logs"

    __table_args__ = (
        # برای گزارش‌گیری سریع
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_created", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)

    # telegram_id ادمینی که action رو انجام داده (اگه admin action بود)
    performed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # جزئیات اضافی به صورت JSON
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # IP یا context اضافی
    context: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} user={self.user_id}>"
