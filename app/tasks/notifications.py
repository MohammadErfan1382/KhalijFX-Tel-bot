from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


def _run(coro):
    """اجرای coroutine در Celery (که sync هست)"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.notifications.notify_admins_new_kyc",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notify_admins_new_kyc(
    self,
    user_telegram_id: int,
    user_name: str,
    document_file_id: str,
) -> None:
    """اطلاع‌رسانی به ادمین‌ها وقتی KYC جدید ثبت میشه"""
    async def _send():
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        from app.bot.keyboards.main import kyc_admin_keyboard

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            for admin_id in settings.admin_user_ids:
                try:
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=document_file_id,
                        caption=(
                            f"🔔 <b>درخواست احراز هویت جدید</b>\n\n"
                            f"👤 نام: {user_name}\n"
                            f"🆔 تلگرام: <code>{user_telegram_id}</code>"
                        ),
                        reply_markup=kyc_admin_keyboard(user_telegram_id),
                    )
                except Exception as e:
                    logger.error(
                        "notify_admin_failed", admin=admin_id, error=str(e)
                    )
        finally:
            await bot.session.close()

    try:
        _run(_send())
    except Exception as exc:
        logger.error("notify_admins_kyc_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.notifications.notify_user_kyc_result",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def notify_user_kyc_result(
    self,
    user_telegram_id: int,
    approved: bool,
    reason: str | None = None,
) -> None:
    """اطلاع‌رسانی به کاربر درباره نتیجه KYC"""
    async def _send():
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode

        bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        try:
            if approved:
                text = (
                    "🎉 <b>احراز هویت شما تایید شد!</b>\n\n"
                    "اکنون می‌توانید:\n"
                    "• سفارش ثبت کنید\n"
                    "• نرخ‌های داخلی صرافی را مشاهده کنید\n\n"
                    "از /start برای بازگشت به منوی اصلی استفاده کنید."
                )
            else:
                text = (
                    "❌ <b>درخواست احراز هویت شما رد شد</b>\n\n"
                    f"دلیل: {reason or 'ذکر نشده'}\n\n"
                    "می‌توانید مدارک جدید ارسال کنید."
                )

            await bot.send_message(chat_id=user_telegram_id, text=text)
        finally:
            await bot.session.close()

    try:
        _run(_send())
    except Exception as exc:
        logger.error("notify_user_kyc_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.notifications.refresh_rates_cache")
def refresh_rates_cache() -> None:
    """Pre-warm کردن cache نرخ ارز - هر ۵۵ ثانیه"""
    async def _refresh():
        from app.services.rate_service import RateService
        service = RateService()
        await service.get_public_rates()

    try:
        _run(_refresh())
        logger.info("rates_cache_refreshed")
    except Exception as e:
        logger.error("rates_cache_refresh_failed", error=str(e))
