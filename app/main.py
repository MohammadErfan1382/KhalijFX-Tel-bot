from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.core.config import settings
from app.core.database import check_db_connection, close_db
from app.core.logging import get_logger, setup_logging
from app.core.redis import check_redis_connection, close_redis, get_fsm_redis

logger = get_logger(__name__)


async def on_startup(bot: Bot) -> None:
    """اجرا میشه وقتی ربات شروع میکنه"""
    logger.info("bot_starting", env=settings.app_env)

    # Health checks
    if not await check_db_connection():
        raise RuntimeError("دیتابیس در دسترس نیست")
    if not await check_redis_connection():
        raise RuntimeError("Redis در دسترس نیست")

    # Migrations رو اجرا میکنیم (فقط در startup)
    await run_migrations()

    if settings.use_webhook:
        await bot.set_webhook(
            url=settings.webhook_url,  # type: ignore
            secret_token=settings.webhook_secret,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
        logger.info("webhook_set", url=settings.webhook_url)
    else:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("polling_mode_enabled")

    me = await bot.get_me()
    logger.info("bot_started", username=me.username, id=me.id)


async def on_shutdown(bot: Bot) -> None:
    """اجرا میشه وقتی ربات خاموش میشه"""
    logger.info("bot_stopping")

    if settings.use_webhook:
        await bot.delete_webhook()

    await close_db()
    await close_redis()
    await bot.session.close()

    logger.info("bot_stopped")


async def run_migrations() -> None:
    """اجرای Alembic migrations در startup"""
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    # در thread جدا چون alembic sync هست
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, command.upgrade, config, "head")
    logger.info("migrations_applied")


async def main() -> None:
    setup_logging()

    # ── Bot instance ──────────────────────────────────────
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # ── FSM Storage (Redis) ───────────────────────────────
    storage = RedisStorage(redis=get_fsm_redis())

    # ── Dispatcher ────────────────────────────────────────
    global dp
    dp = Dispatcher(storage=storage)

    # ── Register Middlewares ───────────────────────────────
    from app.bot.middlewares.db import DbSessionMiddleware
    from app.bot.middlewares.auth import AuthMiddleware
    from app.bot.middlewares.rate_limit import RateLimitMiddleware

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    # ── Register Routers ───────────────────────────────────
    from app.bot.handlers.public import router as public_router
    from app.bot.handlers.kyc import router as kyc_router
    from app.bot.handlers.verified import router as verified_router
    from app.bot.handlers.admin import router as admin_router

    dp.include_router(public_router)
    dp.include_router(kyc_router)
    dp.include_router(verified_router)
    dp.include_router(admin_router)

    # ── Startup / Shutdown hooks ───────────────────────────
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ── Run ───────────────────────────────────────────────
    if settings.use_webhook:
        # TODO: در مرحله بعدی webhook server رو اضافه میکنیم
        pass
    else:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )


if __name__ == "__main__":
    asyncio.run(main())
