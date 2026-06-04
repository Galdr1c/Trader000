"""MCPClient — wraps tradingview-mcp tools for SVTR bot.

Provides caching, rate limiting, and normalized responses
for all tradingview-mcp tools used by the signal scanner.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MCPClient:
    """Client that wraps tradingview-mcp tools for the SVTR bot.

    All calls go through tradingview_mcp.server functions with:
    - TTL caching (configurable per method)
    - Error handling with fallback values
    - Response normalization
    """

    def __init__(self, cache_ttl: float = 60.0) -> None:
        self._cache_ttl = cache_ttl
        self._call_count: int = 0
        self._error_count: int = 0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_calls": self._call_count,
            "error_count": self._error_count,
            "cache_ttl": self._cache_ttl,
        }

    # ── Price ──────────────────────────────────────────────────────

    async def get_price(self, symbol: str) -> dict[str, Any]:
        """Get current price for a symbol via Yahoo Finance.

        Returns dict with keys: price, change_pct, high_52w, low_52w, market_state
        """
        result = await self._call("yahoo_price", symbol=symbol)
        if isinstance(result, dict):
            return {
                "price": result.get("price", 0),
                "change_pct": result.get("change_pct", 0),
                "high_52w": result.get("high_52w", 0),
                "low_52w": result.get("low_52w", 0),
                "market_state": result.get("market_state", "UNKNOWN"),
                "raw": result,
            }
        return {"price": 0, "change_pct": 0}

    # ── Technical Analysis ─────────────────────────────────────────

    async def get_technical_analysis(
        self,
        symbol: str,
        exchange: str = "BINANCE",
        timeframe: str = "4h",
    ) -> dict[str, Any]:
        """Get full technical analysis for a symbol.

        Returns dict with:
          - summary: BUY/SELL/HOLD
          - buy_count, sell_count, neutral_count
          - indicators: dict of individual indicator signals
          - price info
        """
        result = await self._call(
            "analyze_coin",
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        )

        return self.normalize_technical_analysis(result)

    async def get_multi_timeframe_analysis(
        self,
        symbol: str,
        exchange: str = "BINANCE",
    ) -> dict[str, Any]:
        """Get multi-timeframe analysis (15m, 1h, 4h, 1d)."""
        result = await self._call(
            "multi_timeframe_analysis",
            symbol=symbol,
            exchange=exchange,
        )
        return result if isinstance(result, dict) else {}

    # ── Sentiment ──────────────────────────────────────────────────

    async def get_market_sentiment(
        self,
        symbol: str = "BTC",
        category: str = "crypto",
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get Reddit/community sentiment for a symbol.

        Returns dict with: score, bullish_pct, bearish_pct, post_count, top_posts
        """
        result = await self._call(
            "market_sentiment",
            symbol=symbol,
            category=category,
            limit=limit,
        )
        if isinstance(result, dict):
            return {
                "score": result.get("score", 0),
                "bullish_pct": result.get("bullish_pct", 50),
                "bearish_pct": result.get("bearish_pct", 50),
                "post_count": result.get("post_count", 0),
                "top_posts": result.get("top_posts", []),
                "raw": result,
            }
        return {"score": 0, "post_count": 0}

    async def get_news(
        self,
        symbol: str | None = None,
        category: str = "crypto",
        limit: int = 10,
    ) -> list[dict]:
        """Get financial/crypto news."""
        result = await self._call(
            "financial_news",
            symbol=symbol,
            category=category,
            limit=limit,
        )
        if isinstance(result, dict):
            return result.get("articles", [])
        if isinstance(result, list):
            return result
        return []

    # ── Combined Analysis ─────────────────────────────────────────

    async def get_combined_analysis(
        self,
        symbol: str,
        exchange: str = "BINANCE",
        timeframe: str = "4h",
    ) -> dict[str, Any]:
        """Get combined technical + sentiment analysis.

        This is the primary signal source — returns:
          - technical: full TA breakdown
          - sentiment: Reddit/community sentiment
          - news: recent headlines
          - confluence: unified decision
        """
        result = await self._call(
            "combined_analysis",
            symbol=symbol,
            exchange=exchange,
            timeframe=timeframe,
        )
        return result if isinstance(result, dict) else {}

    # ── Utility ────────────────────────────────────────────────────

    async def load_symbols(self, exchange: str = "BINANCE") -> list[str]:
        """Get list of tradeable symbols for an exchange."""
        result = await self._call("load_symbols", exchange=exchange)
        return result if isinstance(result, list) else []

    # ── Internal ──────────────────────────────────────────────────

    async def _call(self, tool: str, **kwargs: Any) -> Any:
        """Call a tradingview_mcp.server tool function off the main thread.

        MCP tools are synchronous (blocking HTTP calls), so we run
        them in a thread executor to avoid blocking the event loop.
        """
        self._call_count += 1
        try:
            import tradingview_mcp.server as mcp_srv

            fn = getattr(mcp_srv, tool, None)
            if fn is None:
                raise AttributeError(f"Tool '{tool}' not found in tradingview_mcp.server")

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: fn(**kwargs))
            return result

        except Exception as e:
            self._error_count += 1
            logger.warning("mcp_call_error | tool=%s | args=%s | err=%s", tool, kwargs, e)
            return {}

    def normalize_technical_analysis(self, raw: dict) -> dict[str, Any]:
        """Normalize technical analysis output to consistent format."""
        # Handle different response shapes from tradingview-mcp
        if not isinstance(raw, dict) or not raw:
            return {"summary": "HOLD", "buy_count": 0, "sell_count": 0, "indicators": {}}

        indicators = raw.get("indicators") or raw.get("technical_indicators") or {}
        summary = raw.get("summary") or raw.get("rating") or raw.get("signal") or "HOLD"

        # Count BUY/SELL/NEUTRAL signals from indicators
        buy_count = 0
        sell_count = 0
        neutral_count = 0
        parsed_indicators: dict[str, Any] = {}

        if isinstance(indicators, dict):
            for name, signal in indicators.items():
                if isinstance(signal, dict):
                    sig = str(signal.get("signal", signal.get("action", "neutral"))).upper()
                else:
                    sig = str(signal).upper()

                parsed_indicators[name] = sig
                if sig in ("BUY", "STRONG_BUY"):
                    buy_count += 1
                elif sig in ("SELL", "STRONG_SELL"):
                    sell_count += 1
                else:
                    neutral_count += 1

        # Also check for top-level buy/sell counts
        buy_count = raw.get("buy_count", raw.get("buy_signals", buy_count))
        sell_count = raw.get("sell_count", raw.get("sell_signals", sell_count))

        # Price data
        price_info = {
            "price": raw.get("price", 0),
            "change": raw.get("change", raw.get("change_pct", 0)),
        }

        return {
            "summary": summary.upper() if isinstance(summary, str) else "HOLD",
            "buy_count": int(buy_count),
            "sell_count": int(sell_count),
            "neutral_count": int(neutral_count),
            "indicators": parsed_indicators,
            "price": price_info,
            "raw": raw,
        }
