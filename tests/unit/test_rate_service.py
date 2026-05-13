from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rate_service import CACHE_KEY_INTERNAL, CACHE_KEY_PUBLIC, RateService


class TestRateService:

    @pytest.fixture
    def service(self) -> RateService:
        return RateService()

    async def test_get_public_rates_from_cache(
        self, service: RateService, mock_cache_redis
    ):
        cached_data = {"USD": "58000.00", "EUR": "63000.00"}
        mock_cache_redis.get = AsyncMock(return_value=json.dumps(cached_data))

        rates = await service.get_public_rates()

        assert "USD" in rates
        assert rates["USD"] == Decimal("58000.00")
        mock_cache_redis.get.assert_called_once_with(CACHE_KEY_PUBLIC)

    async def test_get_public_rates_from_provider_when_cache_miss(
        self, service: RateService, mock_cache_redis
    ):
        mock_cache_redis.get = AsyncMock(return_value=None)

        fake_response = {
            "rates": {
                "USD": 1.0,
                "EUR": 0.92,
                "GBP": 0.79,
                "AED": 3.67,
                "TRY": 34.1,
            }
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value=fake_response)

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            rates = await service.get_public_rates()

        assert "USD" in rates
        assert "EUR" in rates
        mock_cache_redis.setex.assert_called_once()

    async def test_get_public_rates_raises_on_provider_failure(
        self, service: RateService, mock_cache_redis
    ):
        mock_cache_redis.get = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="در دسترس نیست"):
                await service.get_public_rates()

    async def test_get_internal_rates_from_cache(
        self, service: RateService, mock_cache_redis
    ):
        cached = {
            "USD": {"buy": "57500", "sell": "58500", "spread": "1000"},
        }
        mock_cache_redis.get = AsyncMock(return_value=json.dumps(cached))

        rates = await service.get_internal_rates()
        assert "USD" in rates
        assert rates["USD"]["buy"] == Decimal("57500")
        assert rates["USD"]["sell"] == Decimal("58500")

    async def test_set_internal_rates(
        self, service: RateService, mock_cache_redis
    ):
        rates = {"USD": {"buy": "57000", "sell": "59000", "spread": "2000"}}
        await service.set_internal_rates(rates)
        mock_cache_redis.setex.assert_called_once_with(
            CACHE_KEY_INTERNAL,
            86400,
            json.dumps(rates),
        )

    def test_format_rates_message(self, service: RateService):
        rates = {"USD": Decimal("58000"), "EUR": Decimal("63000")}
        msg = service.format_rates_message(rates)
        assert "USD" in msg
        assert "EUR" in msg
        assert "58,000" in msg

    def test_format_internal_rates_message(self, service: RateService):
        rates = {
            "USD": {
                "buy": Decimal("57500"),
                "sell": Decimal("58500"),
                "spread": Decimal("1000"),
            }
        }
        msg = service.format_internal_rates_message(rates)
        assert "USD" in msg
        assert "57,500" in msg
        assert "58,500" in msg
