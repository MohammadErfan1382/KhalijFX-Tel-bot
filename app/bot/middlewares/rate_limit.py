from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import redis_client

logger = get_logger(__name__)

# Lua script برای atomic token bucket در Redis
# این pattern thread-safe هست چون Redis single-threaded است
_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, window)
end

if count > limit then
    local ttl = redis.call('TTL', key)
    return {0, ttl}
end
return {1, 0}
"""


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if user is None:
            return await handler(event, data)

        # ادمین‌ها rate limit ندارن
        if user.telegram_id in settings.admin_user_ids:
            return await handler(event, data)

        key = f"rl:{user.telegram_id}"
        import time
        result = await redis_client.eval(  # type: ignore
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            settings.rate_limit_requests,
            settings.rate_limit_window,
            int(time.time()),
        )

        allowed, retry_after = result[0], result[1]

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                telegram_id=user.telegram_id,
                retry_after=retry_after,
            )
            if isinstance(event, Message):
                await event.answer(
                    f"⚠️ درخواست‌های شما بیش از حد مجاز است.\n"
                    f"لطفاً {retry_after} ثانیه دیگر تلاش کنید.",
                    show_alert=True,
                )
            return

        return await handler(event, data)
