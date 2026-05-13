from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.audit_log import AuditLog


class KYCStatus(str, enum.Enum):
    """وضعیت‌های احراز هویت"""
    PENDING = "pending"          # ثبت‌نام کرده، هنوز درخواست نداده
    SUBMITTED = "submitted"      # مدارک ارسال شده، در انتظار بررسی
    VERIFIED = "verified"        # تایید شده - دسترسی کامل
    REJECTED = "rejected"        # رد شده


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # ── شناسه تلگرام ───────────────────────────────────────
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # ── KYC ────────────────────────────────────────────────
    kyc_status: Mapped[KYCStatus] = mapped_column(
        Enum(KYCStatus), default=KYCStatus.PENDING, nullable=False, index=True
    )
    kyc_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    kyc_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    kyc_reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True  # telegram_id ادمین تایید کننده
    )
    kyc_reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── اطلاعات KYC (رمزگذاری شده در لایه سرویس) ─────────────
    full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # مسیر فایل‌های مدارک در storage
    document_file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Role & Status ──────────────────────────────────────
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.USER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ──────────────────────────────────────
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    # ── Properties ────────────────────────────────────────
    @property
    def is_verified(self) -> bool:
        return self.kyc_status == KYCStatus.VERIFIED

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def display_name(self) -> str:
        if self.full_name:
            return self.full_name
        name = self.first_name
        if self.last_name:
            name = f"{name} {self.last_name}"
        return name

    def __repr__(self) -> str:
        return f"<User tg={self.telegram_id} kyc={self.kyc_status}>"
