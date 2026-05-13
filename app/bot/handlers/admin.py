from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import kyc_admin_keyboard
from app.bot.states import AdminStates
from app.core.config import settings
from app.core.logging import get_logger
from app.models.user import KYCStatus
from app.repositories.user_repo import UserRepository
from app.services.rate_service import RateService
from app.services.user_service import UserService
from app.tasks.notifications import notify_user_kyc_result

router = Router(name="admin")
logger = get_logger(__name__)

_rate_service = RateService()


# ── Admin filter ─────────────────────────────────────────────────────────────
async def admin_filter(message: Message | CallbackQuery) -> bool:
    from_user = message.from_user
    if not from_user:
        return False
    return from_user.id in settings.admin_user_ids


router.message.filter(admin_filter)
router.callback_query.filter(admin_filter)


# ── پنل ادمین ─────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession) -> None:
    service = UserService(session)
    pending = await service.list_pending_kyc()

    text = (
        "<b>🔐 پنل مدیریت</b>\n\n"
        f"📋 درخواست‌های احراز هویت در انتظار: <b>{len(pending)}</b>\n\n"
        "دستورات:\n"
        "/pending_kyc — لیست احراز هویت‌های در انتظار\n"
        "/set_rate — تنظیم نرخ داخلی\n"
        "/stats — آمار کلی"
    )
    await message.answer(text)


@router.message(Command("pending_kyc"))
async def pending_kyc_list(message: Message, session: AsyncSession) -> None:
    service = UserService(session)
    pending = await service.list_pending_kyc()

    if not pending:
        await message.answer("✅ هیچ درخواست در انتظاری وجود ندارد.")
        return

    for user in pending:
        submitted = (
            user.kyc_submitted_at.strftime("%Y-%m-%d %H:%M")
            if user.kyc_submitted_at
            else "—"
        )
        text = (
            f"<b>درخواست احراز هویت</b>\n\n"
            f"👤 نام: <b>{user.full_name or user.first_name}</b>\n"
            f"🆔 تلگرام: <code>{user.telegram_id}</code>\n"
            f"🪪 کد ملی: <code>{'*' * 6 + (user.national_id or '')[-4:]}</code>\n"
            f"📱 موبایل: <code>{user.phone_number or '—'}</code>\n"
            f"📅 ارسال در: {submitted}"
        )

        # ارسال مدرک
        if user.document_file_id:
            await message.answer_photo(
                photo=user.document_file_id,
                caption=text,
                reply_markup=kyc_admin_keyboard(user.telegram_id),
            )
        else:
            await message.answer(
                text,
                reply_markup=kyc_admin_keyboard(user.telegram_id),
            )


# ── تایید KYC ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kyc:approve:"))
async def approve_kyc(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    target_telegram_id = int(callback.data.split(":")[-1])  # type: ignore
    admin_id = callback.from_user.id  # type: ignore

    repo = UserRepository(session)
    target_user = await repo.get_by_telegram_id(target_telegram_id)

    if not target_user:
        await callback.answer("❌ کاربر یافت نشد.", show_alert=True)
        return

    service = UserService(session)
    try:
        await service.approve_kyc(target_user, admin_id)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.message.edit_caption(  # type: ignore
        caption=(callback.message.caption or "") + "\n\n✅ <b>تایید شد</b>",  # type: ignore
    )
    await callback.answer("✅ کاربر تایید شد")

    # اطلاع‌رسانی به کاربر
    notify_user_kyc_result.delay(
        user_telegram_id=target_telegram_id,
        approved=True,
    )

    logger.info("kyc_approved_by_admin", target=target_telegram_id, admin=admin_id)


# ── رد KYC ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kyc:reject:"))
async def reject_kyc_start(
    callback: CallbackQuery, state: FSMContext
) -> None:
    target_telegram_id = int(callback.data.split(":")[-1])  # type: ignore
    await state.set_state(AdminStates.waiting_reject_reason)
    await state.update_data(target_telegram_id=target_telegram_id)

    await callback.message.answer(  # type: ignore
        "❌ دلیل رد شدن را بنویسید:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_reject_reason)
async def reject_kyc_reason(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    target_telegram_id = data["target_telegram_id"]
    reason = message.text or "بدون دلیل"
    admin_id = message.from_user.id  # type: ignore

    await state.clear()

    repo = UserRepository(session)
    target_user = await repo.get_by_telegram_id(target_telegram_id)

    if not target_user:
        await message.answer("❌ کاربر یافت نشد.")
        return

    service = UserService(session)
    await service.reject_kyc(target_user, admin_id, reason)

    await message.answer(f"✅ درخواست کاربر {target_telegram_id} رد شد.")

    notify_user_kyc_result.delay(
        user_telegram_id=target_telegram_id,
        approved=False,
        reason=reason,
    )


# ── تنظیم نرخ داخلی ──────────────────────────────────────────────────────────

@router.message(Command("set_rate"))
async def set_rate_start(message: Message) -> None:
    await message.answer(
        "<b>تنظیم نرخ داخلی</b>\n\n"
        "فرمت JSON وارد کنید:\n"
        "<pre>{\n"
        '  "USD": {"buy": "58000", "sell": "59000", "spread": "1000"},\n'
        '  "EUR": {"buy": "63000", "sell": "64500", "spread": "1500"}\n'
        "}</pre>"
    )


@router.message(AdminStates.waiting_internal_rate)
async def set_rate_apply(message: Message, state: FSMContext) -> None:
    import json
    await state.clear()
    try:
        rates = json.loads(message.text or "")
        await _rate_service.set_internal_rates(rates)
        await message.answer("✅ نرخ‌های داخلی به‌روزرسانی شدند.")
    except (json.JSONDecodeError, Exception) as e:
        await message.answer(f"❌ خطا: {e}")
