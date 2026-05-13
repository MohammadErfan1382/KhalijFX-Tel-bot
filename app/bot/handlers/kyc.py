from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PhotoSize
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import cancel_keyboard, main_menu
from app.bot.states import KYCStates
from app.core.config import settings
from app.core.logging import get_logger
from app.models.user import KYCStatus, User
from app.services.user_service import UserService
from app.tasks.notifications import notify_admins_new_kyc

router = Router(name="kyc")
logger = get_logger(__name__)


# ── شروع فلوی KYC ─────────────────────────────────────────────────────────────

@router.message(
    F.text.in_({"🪪 درخواست احراز هویت", "🔄 ارسال مجدد مدارک"})
)
async def start_kyc(message: Message, user: User, state: FSMContext) -> None:
    if user.kyc_status == KYCStatus.VERIFIED:
        await message.answer("✅ شما قبلاً احراز هویت شده‌اید.")
        return
    if user.kyc_status == KYCStatus.SUBMITTED:
        await message.answer("⏳ مدارک شما در حال بررسی است. لطفاً صبر کنید.")
        return

    await state.set_state(KYCStates.waiting_full_name)
    await message.answer(
        "🪪 <b>فرآیند احراز هویت</b>\n\n"
        "برای دسترسی به امکانات کامل صرافی، لطفاً مراحل زیر را طی کنید.\n\n"
        "<b>مرحله ۱/۴</b>\n"
        "نام و نام خانوادگی خود را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )


# ── مرحله ۱: نام کامل ────────────────────────────────────────────────────────

@router.message(KYCStates.waiting_full_name)
async def kyc_full_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❌ لطفاً نام خود را به صورت متن وارد کنید.")
        return

    name = message.text.strip()
    if len(name) < 4 or len(name) > 100:
        await message.answer("❌ نام باید بین ۴ تا ۱۰۰ کاراکتر باشد.")
        return

    await state.update_data(full_name=name)
    await state.set_state(KYCStates.waiting_national_id)
    await message.answer(
        f"✅ <b>{name}</b>\n\n"
        "<b>مرحله ۲/۴</b>\n"
        "کد ملی ۱۰ رقمی خود را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )


# ── مرحله ۲: کد ملی ──────────────────────────────────────────────────────────

@router.message(KYCStates.waiting_national_id)
async def kyc_national_id(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❌ لطفاً کد ملی را به صورت متن وارد کنید.")
        return

    national_id = message.text.strip().replace("-", "")
    if not national_id.isdigit() or len(national_id) != 10:
        await message.answer("❌ کد ملی باید ۱۰ رقم باشد.")
        return

    await state.update_data(national_id=national_id)
    await state.set_state(KYCStates.waiting_phone)
    await message.answer(
        "<b>مرحله ۳/۴</b>\n"
        "شماره موبایل خود را وارد کنید (مثال: 09121234567):",
        reply_markup=cancel_keyboard(),
    )


# ── مرحله ۳: شماره موبایل ────────────────────────────────────────────────────

@router.message(KYCStates.waiting_phone)
async def kyc_phone(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("❌ لطفاً شماره موبایل را وارد کنید.")
        return

    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not phone.startswith(("09", "+98")) or len(phone.lstrip("+98").lstrip("0")) != 10:
        await message.answer("❌ شماره موبایل معتبر نیست. مثال: 09121234567")
        return

    # نرمال‌سازی به فرمت 09...
    if phone.startswith("+98"):
        phone = "0" + phone[3:]

    await state.update_data(phone_number=phone)
    await state.set_state(KYCStates.waiting_document)
    await message.answer(
        "<b>مرحله ۴/۴</b>\n"
        "تصویر کارت ملی یا گذرنامه خود را ارسال کنید:\n\n"
        "⚠️ تصویر باید واضح و خوانا باشد.",
        reply_markup=cancel_keyboard(),
    )


# ── مرحله ۴: مدرک ────────────────────────────────────────────────────────────

@router.message(KYCStates.waiting_document, F.photo)
async def kyc_document(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    # بهترین کیفیت عکس رو میگیریم (آخرین آیتم)
    photo: PhotoSize = message.photo[-1]  # type: ignore
    file_id = photo.file_id

    data = await state.get_data()
    await state.set_state(KYCStates.waiting_confirm)
    await state.update_data(document_file_id=file_id)

    # نمایش خلاصه برای تایید نهایی
    await message.answer(
        "<b>📋 خلاصه اطلاعات شما</b>\n\n"
        f"👤 نام: <b>{data['full_name']}</b>\n"
        f"🪪 کد ملی: <code>{'*' * 6 + data['national_id'][-4:]}</code>\n"
        f"📱 موبایل: <code>{data['phone_number']}</code>\n"
        f"📄 مدرک: ✅ دریافت شد\n\n"
        "آیا اطلاعات صحیح است؟",
        reply_markup=_confirm_keyboard(),
    )


@router.message(KYCStates.waiting_document)
async def kyc_document_invalid(message: Message) -> None:
    await message.answer("❌ لطفاً تصویر (عکس) ارسال کنید، نه فایل یا متن.")


# ── تایید نهایی ───────────────────────────────────────────────────────────────

@router.callback_query(KYCStates.waiting_confirm, F.data == "kyc:submit")
async def kyc_submit_confirm(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    data = await state.get_data()
    await state.clear()

    service = UserService(session)
    try:
        user = await service.submit_kyc(
            user=user,
            full_name=data["full_name"],
            national_id=data["national_id"],
            phone_number=data["phone_number"],
            document_file_id=data["document_file_id"],
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore
        "✅ <b>مدارک شما با موفقیت ارسال شد</b>\n\n"
        "پس از بررسی توسط کارشناسان (معمولاً ۲۴ ساعت) نتیجه به شما اطلاع داده می‌شود.\n\n"
        "🔔 در صورت تایید، امکان ثبت سفارش و مشاهده نرخ‌های داخلی برای شما فعال می‌شود."
    )

    # اطلاع‌رسانی به ادمین‌ها (Celery task)
    notify_admins_new_kyc.delay(
        user_telegram_id=user.telegram_id,
        user_name=user.display_name,
        document_file_id=data["document_file_id"],
    )

    await callback.answer()


@router.callback_query(KYCStates.waiting_confirm, F.data == "kyc:edit")
async def kyc_submit_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(KYCStates.waiting_full_name)
    await state.clear()
    await callback.message.edit_text(  # type: ignore
        "🔄 فرآیند از ابتدا شروع می‌شود.\n"
        "نام و نام خانوادگی خود را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


# ── لغو FSM در هر مرحله ──────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel:fsm")
async def cancel_fsm(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await state.clear()
    await callback.message.edit_text("❌ عملیات لغو شد.")  # type: ignore
    await callback.answer()


def _confirm_keyboard():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تایید و ارسال", callback_data="kyc:submit"),
        InlineKeyboardButton(text="✏️ ویرایش", callback_data="kyc:edit"),
    )
    return builder.as_markup()
