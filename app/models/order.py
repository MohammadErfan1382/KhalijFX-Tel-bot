from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class OrderType(str, enum.Enum):
    BUY = "buy"      # خرید ارز
    SELL = "sell"    # فروش ارز


class OrderStatus(str, enum.Enum):
    PENDING = "pending"          # ثبت شده، در انتظار پردازش
    PROCESSING = "processing"    # در حال پردازش
    COMPLETED = "completed"      # انجام شده
    CANCELLED = "cancelled"      # لغو شده
    REJECTED = "rejected"        # رد شده توسط صرافی


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    # ── Foreign Key ────────────────────────────────────────
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # ── جزئیات سفارش ────────────────────────────────────────
    order_type: Mapped[OrderType] = mapped_column(
        Enum(OrderType), nullable=False, index=True
    )
    currency_from: Mapped[str] = mapped_column(String(10), nullable=False)  # IRR
    currency_to: Mapped[str] = mapped_column(String(10), nullable=False)    # USD
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)
    rate_at_order: Mapped[Decimal] = mapped_column(DECIMAL(20, 6), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), nullable=False)

    # ── وضعیت ──────────────────────────────────────────────
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False, index=True
    )
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Reference ─────────────────────────────────────────
    # شماره پیگیری برای نمایش به مشتری
    reference_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )

    # ── Relationships ──────────────────────────────────────
    user: Mapped["User"] = relationship(back_populates="orders")

    def __repr__(self) -> str:
        return f"<Order {self.reference_code} {self.order_type} {self.status}>"
