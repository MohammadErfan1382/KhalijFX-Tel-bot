from __future__ import annotations

import json
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import cache_redis

logger = get_logger(__name__)

# نرخ‌های پیش‌فرض صرافی (نرخ داخلی)
# در production این‌ها از یک منبع معتبر میان
SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "AED", "TRY"]

CACHE_KEY_PUBLIC = "rates:public"       # نرخ عمومی (برای همه)
CACHE_KEY_INTERNAL = "rates:internal"   # نرخ داخلی (فقط verified)


class RateService:
    """
    سرویس نرخ ارز با cache دو لایه:
    - نرخ عمومی: از API خارجی، TTL = settings.rate_cache_ttl
    - نرخ داخلی صرافی: دستی تنظیم میشه، TTL بیشتر
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _fetch_from_provider(self) -> dict[str, Decimal]:
        """دریافت نرخ از API خارجی با retry"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                settings.rate_provider_url,
                headers={"Authorization": f"Bearer {settings.rate_provider_api_key}"}
                if settings.rate_provider_api_key
                else {},
            )
            response.raise_for_status()
            data = response.json()

        # ساختار پاسخ ExchangeRate API:
        # {"rates": {"USD": 1.0, "EUR": 0.92, ...}, "base": "USD"}
        raw_rates = data.get("rates", {})
        return {
            currency: Decimal(str(raw_rates[currency]))
            for currency in SUPPORTED_CURRENCIES
            if currency in raw_rates
        }

    async def get_public_rates(self) -> dict[str, Decimal]:
        """
        نرخ‌های عمومی - کش‌شده در Redis.
        هر rate_cache_ttl ثانیه یک‌بار refresh میشه.
        """
        cached = await cache_redis.get(CACHE_KEY_PUBLIC)
        if cached:
            raw = json.loads(cached)
            return {k: Decimal(v) for k, v in raw.items()}

        try:
            rates = await self._fetch_from_provider()
            await cache_redis.setex(
                CACHE_KEY_PUBLIC,
                settings.rate_cache_ttl,
                json.dumps({k: str(v) for k, v in rates.items()}),
            )
            logger.info("rates_refreshed_from_provider", currencies=list(rates.keys()))
            return rates
        except Exception as e:
            logger.error("rate_fetch_failed", error=str(e))
            # اگه cache خالیه و API هم نداد، نرخ آخر رو برمیگردونیم
            raise RuntimeError("سرویس نرخ ارز در حال حاضر در دسترس نیست") from e

    async def get_internal_rates(self) -> dict[str, dict[str, Decimal]]:
        """
        نرخ‌های داخلی صرافی (خرید/فروش).
        فقط برای کاربران verified.
        این نرخ‌ها توسط ادمین دستی تنظیم میشن.
        """
        cached = await cache_redis.get(CACHE_KEY_INTERNAL)
        if cached:
            raw = json.loads(cached)
            return {
                currency: {
                    "buy": Decimal(v["buy"]),
                    "sell": Decimal(v["sell"]),
                    "spread": Decimal(v["spread"]),
                }
                for currency, v in raw.items()
            }

        # اگه ادمین هنوز تنظیم نکرده، نرخ عمومی + spread پیش‌فرض
        public_rates = await self.get_public_rates()
        internal = {}
        for currency, rate in public_rates.items():
            spread = rate * Decimal("0.015")  # ۱.۵٪ spread
            internal[currency] = {
                "buy": rate - spread,
                "sell": rate + spread,
                "spread": spread * 2,
            }
        return internal

    async def set_internal_rates(
        self,
        rates: dict[str, dict[str, str]],
        ttl: int = 86400,
    ) -> None:
        """ادمین نرخ داخلی رو set میکنه"""
        await cache_redis.setex(
            CACHE_KEY_INTERNAL,
            ttl,
            json.dumps(rates),
        )
        logger.info("internal_rates_updated", currencies=list(rates.keys()))

    def format_rates_message(
        self, rates: dict[str, Decimal], title: str = "نرخ ارز"
    ) -> str:
        lines = [f"<b>💱 {title}</b>\n"]
        flags = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "AED": "🇦🇪", "TRY": "🇹🇷"}
        for currency, rate in rates.items():
            flag = flags.get(currency, "")
            lines.append(f"{flag} <b>{currency}</b>: {rate:,.2f} تومان")
        return "\n".join(lines)

    def format_internal_rates_message(
        self, rates: dict[str, dict[str, Decimal]]
    ) -> str:
        lines = ["<b>💼 نرخ‌های داخلی صرافی</b>\n"]
        flags = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "AED": "🇦🇪", "TRY": "🇹🇷"}
        for currency, data in rates.items():
            flag = flags.get(currency, "")
            lines.append(
                f"{flag} <b>{currency}</b>\n"
                f"   خرید: <code>{data['buy']:,.2f}</code>\n"
                f"   فروش: <code>{data['sell']:,.2f}</code>"
            )
        return "\n\n".join(lines)
