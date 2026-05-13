from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import main_menu
from app.models.user import User
from app.services.rate_service import RateService

router = Router(name="public")
_rate_service = RateService()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"سلام <b>{user.first_name}</b>! 👋\n\n"
        "به ربات صرافی خوش آمدید.\n"
        "از منوی زیر استفاده کنید:",
        reply_markup=main_menu(user),
    )


@router.message(Command("help"))
@router.message(lambda m: m.text == "📞 پشتیبانی")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>راهنمای ربات صرافی</b>\n\n"
        "• <b>نرخ ارز</b> — مشاهده نرخ‌های لحظه‌ای\n"
        "• <b>احراز هویت</b> — برای دسترسی به امکانات کامل\n"
        "• <b>ثبت سفارش</b> — پس از احراز هویت\n"
        "• <b>نرخ داخلی</b> — نرخ خرید و فروش صرافی\n\n"
        "📞 پشتیبانی: @support_username"
    )


@router.message(lambda m: m.text == "💱 نرخ ارز")
async def show_rates(message: Message) -> None:
    await message.answer("⏳ در حال دریافت نرخ‌ها...")
    try:
        rates = await _rate_service.get_public_rates()
        text = _rate_service.format_rates_message(rates)
        await message.answer(text)
    except RuntimeError as e:
        await message.answer(f"❌ {e}")


@router.message(lambda m: m.text == "⏳ وضعیت احراز هویت")
async def kyc_status(message: Message, user: User) -> None:
    from app.models.user import KYCStatus
    status_map = {
        KYCStatus.PENDING: "⚪️ هنوز درخواست ندادید",
        KYCStatus.SUBMITTED: "🟡 مدارک در حال بررسی است",
        KYCStatus.VERIFIED: "🟢 تایید شده",
        KYCStatus.REJECTED: (
            f"🔴 رد شده\n"
            f"دلیل: {user.kyc_reject_reason or 'ذکر نشده'}"
        ),
    }
    await message.answer(
        f"<b>وضعیت احراز هویت</b>\n\n"
        f"{status_map[user.kyc_status]}"
    )
