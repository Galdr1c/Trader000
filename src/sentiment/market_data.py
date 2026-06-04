"""Market data collection — funding rate, open interest, volume metrics.

Collects on-chain and derivatives market data from exchange APIs
to enrich signal evaluation with market context.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


async def fetch_funding_rate(
    exchange_client: Any,
    symbol: str,
) -> dict[str, Any]:
    """Fetch current and historical funding rates.

    Returns dict with:
        - current_rate: float (e.g. 0.0001 = 0.01%)
        - is_extreme: bool (above threshold)
        - direction: str ("long_heavy" | "short_heavy" | "neutral")
    """
    try:
        rate = await exchange_client.get_funding_rate(symbol)
        is_extreme = abs(rate) >= settings.funding_rate_alert_threshold

        if rate > 0.001:
            direction = "long_heavy"  # Longs paying shorts → overleveraged longs
        elif rate < -0.001:
            direction = "short_heavy"  # Shorts paying longs → overleveraged shorts
        else:
            direction = "neutral"

        return {
            "current_rate": rate,
            "current_rate_pct": round(rate * 100, 4),
            "is_extreme": is_extreme,
            "direction": direction,
        }
    except Exception as e:
        logger.warning("funding_rate_error | %s | %s", symbol, e)
        return {
            "current_rate": 0.0,
            "current_rate_pct": 0.0,
            "is_extreme": False,
            "direction": "unknown",
        }


async def fetch_open_interest(
    exchange_client: Any,
    symbol: str,
) -> dict[str, Any]:
    """Fetch open interest data.

    Returns dict with:
        - current_oi: float (in contracts/coins)
        - oi_change_pct: float (estimated from position changes)
        - signal: str ("increasing" | "decreasing" | "flat")
    """
    try:
        # Use ExchangeClient method if available, fall back to ccxt directly
        if hasattr(exchange_client, 'get_open_interest'):
            oi_data = await exchange_client.get_open_interest(symbol)
        else:
            # Fallback: access ccxt exchange directly
            oi_data = await exchange_client.exchange.fetch_open_interest(symbol)
        current_oi = float(oi_data.get("openInterestAmount", 0))

        return {
            "current_oi": current_oi,
            "oi_change_pct": 0.0,  # Would need historical data for true change
            "signal": "flat",
            "base_currency": oi_data.get("baseVolume", ""),
            "quote_currency": oi_data.get("quoteVolume", ""),
        }
    except AttributeError:
        # Exchange doesn't support fetchOpenInterest
        logger.debug("open_interest_not_supported | %s", symbol)
        return {
            "current_oi": 0.0,
            "oi_change_pct": 0.0,
            "signal": "unknown",
        }
    except Exception as e:
        logger.warning("open_interest_error | %s | %s", symbol, e)
        return {
            "current_oi": 0.0,
            "oi_change_pct": 0.0,
            "signal": "unknown",
        }


async def fetch_volume_analysis(
    exchange_client: Any,
    symbol: str,
    timeframe: str = "1h",
) -> dict[str, Any]:
    """Fetch volume metrics for the symbol.

    Returns dict with:
        - current_volume: float
        - avg_volume: float (20-period average)
        - volume_ratio: float (current/avg)
        - is_high_volume: bool
    """
    try:
        # Fetch recent candles to calculate volume metrics
        ohlcv = await exchange_client.get_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=25,
        )

        if not ohlcv or len(ohlcv) < 2:
            return {
                "current_volume": 0.0,
                "avg_volume": 0.0,
                "volume_ratio": 1.0,
                "is_high_volume": False,
            }

        # Last candle volume = current
        current_volume = float(ohlcv[-1][5])

        # Average of previous 20 candles (excluding current)
        prev_volumes = [float(c[5]) for c in ohlcv[-21:-1]]
        avg_volume = sum(prev_volumes) / len(prev_volumes) if prev_volumes else 1.0

        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        return {
            "current_volume": current_volume,
            "avg_volume": round(avg_volume, 2),
            "volume_ratio": round(volume_ratio, 2),
            "is_high_volume": volume_ratio > 1.5,
        }
    except Exception as e:
        logger.warning("volume_analysis_error | %s | %s", symbol, e)
        return {
            "current_volume": 0.0,
            "avg_volume": 0.0,
            "volume_ratio": 1.0,
            "is_high_volume": False,
        }


async def fetch_market_context(
    exchange_client: Any,
    symbol: str,
) -> dict[str, Any]:
    """Collect all market context data in a single call.

    Aggregates funding rate, open interest, and volume metrics.
    Used by the decision engine to enrich AI evaluation.
    """
    funding_task = fetch_funding_rate(exchange_client, symbol)
    oi_task = fetch_open_interest(exchange_client, symbol)
    volume_task = fetch_volume_analysis(exchange_client, symbol)

    funding, oi, volume = await asyncio.gather(
        funding_task, oi_task, volume_task
    )

    context: dict[str, Any] = {
        "funding_rate": funding["current_rate"],
        "funding_rate_pct": funding["current_rate_pct"],
        "funding_is_extreme": funding["is_extreme"],
        "funding_direction": funding["direction"],
        "open_interest": oi["current_oi"],
        "oi_change_pct": oi["oi_change_pct"],
        "oi_signal": oi["signal"],
        "volume_ratio": volume["volume_ratio"],
        "is_high_volume": volume["is_high_volume"],
    }

    logger.info(
        "market_context_fetched | symbol=%s | funding=%.4f%% | oi=%.0f | vol_ratio=%.2f",
        symbol,
        funding["current_rate_pct"],
        oi["current_oi"],
        volume["volume_ratio"],
    )

    return context
