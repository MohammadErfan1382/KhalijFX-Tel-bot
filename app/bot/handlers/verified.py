from __future__ import annotations

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import (
    cancel_keyboard,
    confirm_order_keyboard,
    currency_keyboard,
    main_menu,
    order_type_keyboard,
)
from app.bot.states import OrderStates
from app.core.logging import get_logger
from app.models.order import OrderType
from app.models.user import KYCStatus, User
from app.services.order_service import OrderService
from app.services.rate_service import RateService

router = Router(name="verified")
logger = get_logger(__name__)

_rate_service = RateService()

# ── Filter: فقط کاربران verified ─────────────────────────────────────────────
# این filter رو روی router میذاریم تا همه handler های این فایل فقط برای verified باشن


async def verified_filter(message: Message, user: User) -> bool:
    return user.kyc_status == KYCStatus.VERIFIED


# ── نرخ داخلی ─────────────────────────────────────────────────────────────────

@router.message(F.text == "💼 نرخ داخلی")
async def show_internal_rates(message: Message, user: User) -> None:
    if user.kyc_status != KYCStatus.VERIFIED:
        await message.answer("❌ برای مشاهده نرخ داخلی باید احراز هویت شوید.")
        return

    await message.answer("⏳ در حال دریافت نرخ‌های داخلی...")
    try:
        rates = await _rate_service.get_internal_rates()
        text = _rate_service.format_internal_rates_message(rates)
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ خطا: {e}")


# ── شروع ثبت سفارش ───────────────────────────────────────────────────────────

@router.message(F.text == "📋 ثبت سفارش")
async def start_order(message: Message, user: User, state: FSMContext) -> None:
    if user.kyc_status != KYCStatus.VERIFIED:
        await message.answer(
            "❌ برای ثبت سفارش باید احراز هویت شوید.\n"
            "از گزینه «احراز هویت» استفاده کنید."
        )
        return

    await state.set_state(OrderStates.selecting_type)
    await message.answer(
        "<b>📋 ثبت سفارش جدید</b>\n\nنوع معامله را انتخاب کنید:",
        reply_markup=order_type_keyboard(),
    )


# ── انتخاب نوع سفارش ─────────────────────────────────────────────────────────

@router.callback_query(OrderStates.selecting_type, F.data.startswith("order:"))
async def select_order_type(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":")[1]  # type: ignore

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ ثبت سفارش لغو شد.")  # type: ignore
        await callback.answer()
        return

    order_type = OrderType.BUY if action == "buy" else OrderType.SELL
    await state.update_data(order_type=order_type.value)
    await state.set_state(OrderStates.selecting_currency)

    type_text = "خرید" if order_type == OrderType.BUY else "فروش"
    await callback.message.edit_text(  # type: ignore
        f"<b>📋 سفارش {type_text}</b>\n\nارز مورد نظر را انتخاب کنید:",
        reply_markup=currency_keyboard(action),
    )
    await callback.answer()


# ── انتخاب ارز ───────────────────────────────────────────────────────────────

@router.callback_query(
    OrderStates.selecting_currency, F.data.startswith("currency:")
)
async def select_currency(callback: CallbackQuery, state: FSMContext) -> None:
    _, order_type_str, currency = callback.data.split(":")  # type: ignore

    # دریافت نرخ لحظه‌ای
    try:
        internal_rates = await _rate_service.get_internal_rates()
        rate_data = internal_rates.get(currency)
        if not rate_data:
            await callback.answer("❌ این ارز در حال حاضر موجود نیست.", show_alert=True)
            return
    except Exception:
        await callback.answer("❌ خطا در دریافت نرخ.", show_alert=True)
        return

    order_type = OrderType(order_type_str)
    rate = rate_data["buy"] if order_type == OrderType.BUY else rate_data["sell"]

    await state.update_data(currency=currency, rate=str(rate))
    await state.set_state(OrderStates.entering_amount)

    type_text = "خرید" if order_type == OrderType.BUY else "فروش"
    await callback.message.edit_text(  # type: ignore
        f"<b>📋 سفارش {type_text} {currency}</b>\n\n"
        f"📊 نرخ فعلی: <code>{rate:,.2f}</code> تومان\n\n"
        f"مقدار {currency} مورد نظر را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ── وارد کردن مقدار ──────────────────────────────────────────────────────────

@router.message(OrderStates.entering_amount)
async def enter_amount(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    if not message.text:
        await message.answer("❌ لطفاً مقدار را وارد کنید.")
        return

    try:
        amount = Decimal(message.text.strip().replace(",", ""))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer("❌ مقدار وارد شده معتبر نیست. لطفاً یک عدد مثبت وارد کنید.")
        return

    data = await state.get_data()
    rate = Decimal(data["rate"])
    total = amount * rate
    currency = data["currency"]
    order_type = OrderType(data["order_type"])

    await state.update_data(amount=str(amount))
    await state.set_state(OrderStates.confirming)

    type_text = "خرید" if order_type == OrderType.BUY else "فروش"

    # ساخت reference موقت برای نمایش - سفارش هنوز ثبت نشده
    await state.update_data(confirmed=False)

    await message.answer(
        f"<b>📋 تایید سفارش {type_text}</b>\n\n"
        f"💱 ارز: <b>{currency}</b>\n"
        f"📊 نرخ: <code>{rate:,.2f}</code> تومان\n"
        f"💰 مقدار: <code>{amount:,}</code> {currency}\n"
        f"💵 مبلغ کل: <code>{total:,.0f}</code> تومان\n\n"
        "آیا این سفارش را تایید می‌کنید؟",
        reply_markup=_confirm_order_inline(),
    )


# ── تایید نهایی سفارش ────────────────────────────────────────────────────────

@router.callback_query(OrderStates.confirming, F.data == "order:final_confirm")
async def confirm_order_final(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    data = await state.get_data()
    await state.clear()

    service = OrderService(session)
    try:
        order = await service.create_order(
            user=user,
            order_type=OrderType(data["order_type"]),
            currency_from="IRR",
            currency_to=data["currency"],
            amount=Decimal(data["amount"]),
            rate=Decimal(data["rate"]),
        )
    except (PermissionError, ValueError) as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore
        "✅ <b>سفارش شما با موفقیت ثبت شد</b>\n\n"
        f"🔖 کد پیگیری: <code>{order.reference_code}</code>\n\n"
        "کارشناسان ما در اسرع وقت با شما تماس خواهند گرفت."
    )
    await callback.answer("✅ سفارش ثبت شد")


@router.callback_query(OrderStates.confirming, F.data == "order:cancel_confirm")
async def cancel_order_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ ثبت سفارش لغو شد.")  # type: ignore
    await callback.answer()


# ── لیست سفارش‌ها ─────────────────────────────────────────────────────────────

@router.message(F.text == "📜 سفارش‌های من")
async def my_orders(message: Message, user: User, session: AsyncSession) -> None:
    if user.kyc_status != KYCStatus.VERIFIED:
        await message.answer("❌ برای مشاهده سفارش‌ها باید احراز هویت شوید.")
        return

    service = OrderService(session)
    orders = await service.get_user_orders(user, limit=10)

    if not orders:
        await message.answer("📭 شما هنوز سفارشی ثبت نکرده‌اید.")
        return

    text = "<b>📜 آخرین سفارش‌های شما</b>\n\n"
    for order in orders:
        text += service.format_order_summary(order) + "\n\n" + "─" * 20 + "\n\n"

    await message.answer(text)


def _confirm_order_inline():
    from aiogram.types import InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تایید", callback_data="order:final_confirm"),
        InlineKeyboardButton(text="❌ لغو", callback_data="order:cancel_confirm"),
    )
    return builder.as_markup()
