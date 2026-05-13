from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.audit_log import AuditAction
from app.models.order import Order, OrderStatus, OrderType
from app.models.user import KYCStatus, User
from app.repositories.audit_repo import AuditRepository
from app.repositories.order_repo import OrderRepository

logger = get_logger(__name__)


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.order_repo = OrderRepository(session)
        self.audit_repo = AuditRepository(session)

    async def create_order(
        self,
        user: User,
        order_type: OrderType,
        currency_from: str,
        currency_to: str,
        amount: Decimal,
        rate: Decimal,
    ) -> Order:
        # ── Validations ───────────────────────────────────
        if user.kyc_status != KYCStatus.VERIFIED:
            raise PermissionError("برای ثبت سفارش باید احراز هویت انجام دهید")

        if amount <= 0:
            raise ValueError("مقدار سفارش باید بیشتر از صفر باشد")

        today_count = await self.order_repo.count_today_orders(user.id)
        if today_count >= settings.max_orders_per_day:
            raise ValueError(
                f"سقف روزانه سفارش ({settings.max_orders_per_day} سفارش) "
                "تکمیل شده است"
            )

        # ── Create ────────────────────────────────────────
        total = amount * rate
        order = await self.order_repo.create(
            user_id=user.id,
            order_type=order_type,
            currency_from=currency_from,
            currency_to=currency_to,
            amount=amount,
            rate_at_order=rate,
            total_amount=total,
        )

        await self.audit_repo.log(
            user_id=user.id,
            action=AuditAction.ORDER_CREATED,
            metadata={
                "reference": order.reference_code,
                "type": order_type.value,
                "currency_from": currency_from,
                "currency_to": currency_to,
                "amount": str(amount),
            },
        )

        logger.info(
            "order_created",
            reference=order.reference_code,
            user=user.telegram_id,
            type=order_type.value,
            amount=str(amount),
        )
        return order

    async def get_user_orders(
        self, user: User, limit: int = 10
    ) -> list[Order]:
        return await self.order_repo.get_user_orders(user.id, limit=limit)

    async def cancel_order(self, user: User, reference_code: str) -> Order:
        order = await self.order_repo.get_by_reference(reference_code)

        if not order:
            raise ValueError("سفارش یافت نشد")
        if order.user_id != user.id:
            raise PermissionError("این سفارش متعلق به شما نیست")
        if order.status != OrderStatus.PENDING:
            raise ValueError("فقط سفارش‌های در انتظار قابل لغو هستند")

        order = await self.order_repo.update_status(order, OrderStatus.CANCELLED)

        await self.audit_repo.log(
            user_id=user.id,
            action=AuditAction.ORDER_CANCELLED,
            metadata={"reference": reference_code},
        )
        return order

    def format_order_summary(self, order: Order) -> str:
        type_emoji = "🟢" if order.order_type == OrderType.BUY else "🔴"
        type_text = "خرید" if order.order_type == OrderType.BUY else "فروش"
        status_map = {
            OrderStatus.PENDING: "⏳ در انتظار",
            OrderStatus.PROCESSING: "🔄 در حال پردازش",
            OrderStatus.COMPLETED: "✅ انجام شده",
            OrderStatus.CANCELLED: "❌ لغو شده",
            OrderStatus.REJECTED: "🚫 رد شده",
        }
        return (
            f"{type_emoji} <b>سفارش {type_text}</b>\n"
            f"🔖 کد پیگیری: <code>{order.reference_code}</code>\n"
            f"💱 {order.currency_from} ← {order.currency_to}\n"
            f"💰 مقدار: <code>{order.amount:,.2f}</code>\n"
            f"📊 نرخ: <code>{order.rate_at_order:,.2f}</code>\n"
            f"💵 جمع کل: <code>{order.total_amount:,.2f}</code>\n"
            f"📋 وضعیت: {status_map.get(order.status, order.status.value)}\n"
            f"🕐 تاریخ: {order.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
