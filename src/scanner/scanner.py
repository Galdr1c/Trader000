"""SignalScanner — periodic market scanning via tradingview-mcp.

Runs on a configurable interval, fetches technical analysis + price +
sentiment from MCP tools, computes signal scores, and feeds them
through the DecisionEngine pipeline — no TradingView webhooks needed.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.mcp_provider.client import MCPClient
from src.webhook.models import SignalDirection, TVAlertPayload

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a single scan cycle."""

    symbol: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signal_score: float = 0.0
    direction: str = "hold"
    summary: str = "HOLD"
    analysis: dict[str, Any] = field(default_factory=dict)
    price: float = 0.0
    sentiment: dict[str, Any] = field(default_factory=dict)
    action: str = "none"
    reason: str = ""


def compute_signal_score(analysis: dict[str, Any]) -> tuple[float, str, float]:
    """Compute signal score and direction from technical analysis data.

    Maps MCP technical analysis BUY/SELL counts to the SVTR
    0-13.5 signal score format.

    Returns: (signal_score_0_13.5, direction_long/short, confidence_0_1)
    """
    buy_count = analysis.get("buy_count", 0)
    sell_count = analysis.get("sell_count", 0)
    neutral_count = analysis.get("neutral_count", 0)
    total = buy_count + sell_count + neutral_count

    if total == 0:
        return 5.0, "hold", 0.3

    # Net signal strength: -1.0 to +1.0
    net = (buy_count - sell_count) / max(1, total)

    # Map to 0-13.5 scale (center = 6.75)
    # 13.5 = all BUY, 0 = all SELL, 6.75 = neutral
    signal_score = 6.75 + (net * 6.75)
    signal_score = max(0.0, min(13.5, signal_score))

    # Direction
    threshold = 0.15  # minimum net bias to trigger a direction
    if net > threshold:
        direction = "long"
    elif net < -threshold:
        direction = "short"
    else:
        direction = "hold"

    # Confidence based on total signals and strength
    confidence = min(1.0, (total / 20) * abs(net))

    return round(signal_score, 2), direction, round(confidence, 3)


class SignalScanner:
    """Background scanner that periodically fetches market data via MCP.

    Architecture:
        Timer → MCPClient.get_combined_analysis() → compute_signal_score()
        → TVAlertPayload → DecisionEngine.evaluate_alert() → Trade
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        decision_engine: Any = None,  # DecisionEngine
        interval_seconds: int = 300,  # 5 min default
        symbols: list[str] | None = None,
        max_concurrency: int = 3,
    ) -> None:
        self._mcp = mcp_client
        self._engine = decision_engine
        self._interval = interval_seconds
        self._symbols = symbols or [settings.trading_symbol.split(":")[0]]
        self._max_concurrency = max(1, max_concurrency)
        self._task: asyncio.Task | None = None
        self._running = False

        # Scan history (ring buffer)
        self._history: deque[ScanResult] = deque(maxlen=50)

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def interval_seconds(self) -> int:
        return self._interval
    def is_running(self) -> bool:
        return self._running

    @property
    def last_scan(self) -> ScanResult | None:
        return self._history[-1] if self._history else None

    @property
    def scan_history(self) -> list[ScanResult]:
        return list(self._history)

    def get_scan_history(self, symbol: str | None = None) -> list[ScanResult]:
        """Return all recent results or only results for one symbol."""
        history = list(self._history)
        if symbol is None:
            return history
        return [result for result in history if result.symbol == symbol]

    def set_engine(self, engine: Any) -> None:
        """Inject decision engine (called at startup)."""
        self._engine = engine

    async def start(self) -> None:
        """Start the background scanning loop."""
        if self._running:
            logger.warning("scanner_already_running")
            return
        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info(
            "scanner_started | interval=%ds | symbols=%s",
            self._interval,
            self._symbols,
        )

    async def stop(self) -> None:
        """Stop the background scanning loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("scanner_stopped")

    async def _scan_loop(self) -> None:
        """Main scanning loop — runs forever until stopped."""
        while self._running:
            try:
                await self._run_scan_cycle()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scan_cycle_error | %s", e, exc_info=True)

            # Wait for next interval
            await asyncio.sleep(self._interval)

    async def scan_once(self) -> list[ScanResult]:
        """Run a single scan cycle (for manual/API triggers)."""
        return await self._run_scan_cycle()

    async def _run_scan_cycle(self) -> list[ScanResult]:
        """Scan configured symbols concurrently and process results in order."""
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def scan_guarded(symbol: str) -> ScanResult:
            async with semaphore:
                try:
                    return await self._scan_symbol(symbol)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("scan_symbol_error | symbol=%s | err=%s", symbol, exc)
                    return ScanResult(symbol=symbol, reason=f"scan_error: {exc}")

        results = await asyncio.gather(*(scan_guarded(symbol) for symbol in self._symbols))
        for result in results:
            self._add_to_history(result)
            if result.signal_score >= settings.min_signal_score and result.direction != "hold":
                try:
                    await self._evaluate_trade(result)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error(
                        "scan_evaluation_error | symbol=%s | err=%s",
                        result.symbol,
                        exc,
                    )
                    result.action = "failed"
                    result.reason = f"evaluation_error: {exc}"
            else:
                logger.info(
                    "scan_skip | symbol=%s | score=%.1f | dir=%s | below threshold=%.1f",
                    result.symbol,
                    result.signal_score,
                    result.direction,
                    settings.min_signal_score,
                )
        return results

    async def _scan_symbol(self, symbol: str) -> ScanResult:
        """Scan a single symbol and return the result."""
        # Map symbol format: "BTCUSDT" → "BTC-USD" for MCP tools
        mcp_symbol = self._to_mcp_symbol(symbol)

        try:
            # Fetch combined analysis (technical + sentiment + news)
            analysis = await self._mcp.get_combined_analysis(
                symbol=mcp_symbol,
                exchange=settings.exchange_id.upper(),
                timeframe=settings.timeframe.value,
            )

            # Extract technical analysis from combined result
            tech = analysis.get("technical", analysis.get("analysis", {}))
            if isinstance(tech, dict):
                normalized = self._mcp.normalize_technical_analysis(tech)
            else:
                # Fallback: direct technical analysis call
                normalized = await self._mcp.get_technical_analysis(
                    symbol=mcp_symbol,
                    exchange=settings.exchange_id.upper(),
                    timeframe=settings.timeframe.value,
                )

            # Get price
            price_data = await self._mcp.get_price(mcp_symbol)
            price = price_data.get("price", 0)

            # Get sentiment
            sentiment = await self._mcp.get_market_sentiment(
                symbol=mcp_symbol.replace("-", ""),
                category="crypto",
                limit=10,
            )

            # Compute signal score
            signal_score, direction, _ = compute_signal_score(normalized)
            summary = normalized.get("summary", "HOLD")

            logger.info(
                "scan_result | symbol=%s | score=%.1f | dir=%s | summary=%s | price=%.2f",
                symbol, signal_score, direction, summary, price,
            )

            return ScanResult(
                symbol=symbol,
                signal_score=signal_score,
                direction=direction,
                summary=summary,
                analysis=normalized,
                price=price,
                sentiment=sentiment,
            )

        except Exception as e:
            logger.error("scan_symbol_error | symbol=%s | err=%s", symbol, e, exc_info=True)
            return ScanResult(
                symbol=symbol,
                reason=f"scan_error: {e}",
            )

    async def _evaluate_trade(self, result: ScanResult) -> None:
        """Feed a scan result into the decision engine."""
        if self._engine is None:
            logger.info("scan_no_engine | symbol=%s | score=%.1f", result.symbol, result.signal_score)
            result.action = "simulated"
            result.reason = "no_engine"
            return

        # Build synthetic TVAlertPayload from scan data
        if result.price <= 0:
            logger.warning("scan_skip_no_price | symbol=%s | score=%.1f", result.symbol, result.signal_score)
            result.action = "skipped"
            result.reason = "no_price_data"
            return

        payload = TVAlertPayload(
            symbol=result.symbol,
            direction=SignalDirection.LONG if result.direction == "long" else SignalDirection.SHORT,
            price=result.price,
            signal_score=result.signal_score,
            tp_distance=settings.take_profit_pct,
            message=f"MCP scan: {result.summary} | price={result.price:.2f}",
        )

        engine_result = await self._engine.evaluate_alert(payload)
        result.action = engine_result.get("action", "none")
        result.reason = engine_result.get("reason", "")

    def _add_to_history(self, result: ScanResult) -> None:
        """Add scan result to ring buffer."""
        self._history.append(result)

    @staticmethod
    def _to_mcp_symbol(symbol: str) -> str:
        """Convert SVTR symbol format to MCP format.

        SVTR: "BTCUSDT", "ETHUSDT"
        MCP:  "BTC-USD", "ETH-USD"
        """
        s = symbol.upper().replace("/", "").replace(":", "")
        if "USDT" in s or "USD" in s:
            base = s.replace("USDT", "").replace("USD", "")
            return f"{base}-USD"
        return s
