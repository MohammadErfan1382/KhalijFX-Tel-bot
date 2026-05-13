from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.models.user import KYCStatus, User


def main_menu(user: User) -> ReplyKeyboardMarkup:
    """منوی اصلی بر اساس وضعیت کاربر"""
    builder = ReplyKeyboardBuilder()

    builder.row(KeyboardButton(text="💱 نرخ ارز"))

    if user.kyc_status == KYCStatus.VERIFIED:
        builder.row(
            KeyboardButton(text="📋 ثبت سفارش"),
            KeyboardButton(text="💼 نرخ داخلی"),
        )
        builder.row(KeyboardButton(text="📜 سفارش‌های من"))
    elif user.kyc_status == KYCStatus.PENDING:
        builder.row(KeyboardButton(text="🪪 درخواست احراز هویت"))
    elif user.kyc_status == KYCStatus.SUBMITTED:
        builder.row(KeyboardButton(text="⏳ وضعیت احراز هویت"))
    elif user.kyc_status == KYCStatus.REJECTED:
        builder.row(KeyboardButton(text="🔄 ارسال مجدد مدارک"))

    builder.row(KeyboardButton(text="📞 پشتیبانی"))

    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def order_type_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 خرید", callback_data="order:buy"),
        InlineKeyboardButton(text="🔴 فروش", callback_data="order:sell"),
    )
    builder.row(InlineKeyboardButton(text="❌ انصراف", callback_data="order:cancel"))
    return builder.as_markup()


def currency_keyboard(order_type: str) -> InlineKeyboardMarkup:
    currencies = [
        ("🇺🇸 دلار (USD)", "USD"),
        ("🇪🇺 یورو (EUR)", "EUR"),
        ("🇬🇧 پوند (GBP)", "GBP"),
        ("🇦🇪 درهم (AED)", "AED"),
        ("🇹🇷 لیر (TRY)", "TRY"),
    ]
    builder = InlineKeyboardBuilder()
    for label, code in currencies:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=f"currency:{order_type}:{code}",
            )
        )
    builder.row(InlineKeyboardButton(text="❌ انصراف", callback_data="order:cancel"))
    return builder.as_markup()


def confirm_order_keyboard(reference: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تایید", callback_data=f"confirm:{reference}"),
        InlineKeyboardButton(text="❌ لغو", callback_data=f"cancel:{reference}"),
    )
    return builder.as_markup()


def kyc_admin_keyboard(user_telegram_id: int) -> InlineKeyboardMarkup:
    """کیبورد ادمین برای تایید/رد KYC"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ تایید",
            callback_data=f"kyc:approve:{user_telegram_id}",
        ),
        InlineKeyboardButton(
            text="❌ رد",
            callback_data=f"kyc:reject:{user_telegram_id}",
        ),
    )
    return builder.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ انصراف", callback_data="cancel:fsm"))
    return builder.as_markup()
