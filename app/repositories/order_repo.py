from __future__ import annotations

import random
import string
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderStatus, OrderType


def _generate_reference_code() -> str:
    """کد پیگیری ۱۰ کاراکتری - حروف بزرگ + عدد"""
    chars = string.ascii_uppercase + string.digits
    return "EX-" + "".join(random.choices(chars, k=7))


class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        order_type: OrderType,
        currency_from: str,
        currency_to: str,
        amount: Decimal,
        rate_at_order: Decimal,
        total_amount: Decimal,
    ) -> Order:
        # reference code unique بودنش رو guarantee میکنیم
        for _ in range(5):
            ref = _generate_reference_code()
            existing = await self.get_by_reference(ref)
            if not existing:
                break

        order = Order(
            user_id=user_id,
            order_type=order_type,
            currency_from=currency_from,
            currency_to=currency_to,
            amount=amount,
            rate_at_order=rate_at_order,
            total_amount=total_amount,
            reference_code=ref,
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def get_by_id(self, order_id: UUID) -> Order | None:
        result = await self.session.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_reference(self, reference_code: str) -> Order | None:
        result = await self.session.execute(
            select(Order).where(Order.reference_code == reference_code)
        )
        return result.scalar_one_or_none()

    async def get_user_orders(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_today_orders(self, user_id: UUID) -> int:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self.session.execute(
            select(func.count(Order.id))
            .where(Order.user_id == user_id)
            .where(Order.created_at >= today_start)
            .where(Order.status.notin_([OrderStatus.CANCELLED, OrderStatus.REJECTED]))
        )
        return result.scalar_one()

    async def update_status(
        self,
        order: Order,
        status: OrderStatus,
        reject_reason: str | None = None,
    ) -> Order:
        order.status = status
        if reject_reason:
            order.reject_reason = reject_reason
        await self.session.flush()
        return order
