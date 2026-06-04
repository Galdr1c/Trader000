"""Exchange client — ccxt unified API wrapper for Binance Futures."""

from __future__ import annotations

import logging
from typing import Any

import ccxt.async_support as ccxt

from src.config import settings

logger = logging.getLogger(__name__)


class ExchangeClient:
    """Async wrapper around ccxt for Binance Futures operations."""

    def __init__(self) -> None:
        exchange_class = getattr(ccxt, settings.exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Unsupported exchange: {settings.exchange_id}")

        self.exchange: ccxt.Exchange = exchange_class({
            "apiKey": settings.exchange_api_key,
            "secret": settings.exchange_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
                "adjustForTimeDifference": True,
            },
        })

        if settings.exchange_testnet:
            self.exchange.set_sandbox_mode(True)
            logger.info("exchange_sandbox_mode | %s", settings.exchange_id)

    async def initialize(self) -> None:
        """Load markets."""
        await self.exchange.load_markets()
        logger.info("exchange_initialized | %d markets loaded", len(self.exchange.markets))

    async def close(self) -> None:
        """Close the exchange connection."""
        await self.exchange.close()

    async def get_ticker(self, symbol: str) -> dict[str, Any]:
        """Get current ticker data."""
        return await self.exchange.fetch_ticker(symbol)

    async def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        return await self.exchange.fetch_balance()

    async def get_positions(self, symbol: str | None = None) -> list[dict]:
        """Get open positions."""
        positions = await self.exchange.fetch_positions([symbol] if symbol else None)
        return [p for p in positions if float(p.get("contracts", 0)) > 0]

    async def get_funding_rate(self, symbol: str) -> float:
        """Get current funding rate for a symbol."""
        try:
            info = await self.exchange.fetch_funding_rate(symbol)
            return float(info.get("fundingRate", 0))
        except Exception as e:
            logger.warning("funding_rate_error | %s | %s", symbol, e)
            return 0.0

    async def get_ohlcv(
        self, symbol: str, timeframe: str = "4h", limit: int = 200
    ) -> list[list]:
        """Fetch OHLCV candlestick data."""
        return await self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
