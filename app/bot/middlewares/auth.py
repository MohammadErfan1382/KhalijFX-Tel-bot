from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.repositories.user_repo import UserRepository

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    کاربر رو از دیتابیس لود میکنه (یا میسازه).
    بعد از DbSessionMiddleware اجرا میشه.

    data['user'] = User instance یا None
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]
        tg_user: TgUser | None = data.get("event_from_user")

        if tg_user is None or tg_user.is_bot:
            data["user"] = None
            return await handler(event, data)

        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(tg_user.id)

        if user is None:
            # اولین بار - ثبت کاربر
            user = await repo.create(
                telegram_id=tg_user.id,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )
            logger.info("new_user_registered", telegram_id=tg_user.id)

        # بررسی block
        if user.is_blocked:
            logger.warning("blocked_user_attempted_access", telegram_id=tg_user.id)
            return  # هیچ جوابی نمیدیم

        data["user"] = user
        return await handler(event, data)
