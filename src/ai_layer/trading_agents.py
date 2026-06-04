"""TradingAgents Decision Client — multi-agent LLM trading decision layer.

Wraps the TauricResearch/TradingAgents framework (81k ⭐) for SVTR bot.

Architecture:
    SVTR SignalScanner → MCP data → CompositeScorer
         ↓                            ↓
    TradingAgents (multi-agent LLM debate)
         ↓
    TradeRecommendation → DecisionEngine → Order

TradingAgents runs a full trading firm simulation:
  - Fundamental, Sentiment, News, Technical analysts
  - Bull/Bear researchers (debate)
  - Research Manager, Risk Manager, Portfolio Manager
  - Trader Agent (final decision)
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)


class TradingAgentsDecisionClient:
    """Client that wraps TradingAgents for SVTR bot integration.

    Translates between TradingAgents' TradeRecommendation format
    and SVTR's internal decision dict expected by DecisionEngine.

    Usage:
        client = TradingAgentsDecisionClient(anthropic_api_key=settings.anthropic_api_key)
        decision = await client.analyze("BTC", "2026-06-04")
        # decision = {"approved": True, "confidence": 85, "direction": "long", ...}
    """

    def __init__(
        self,
        anthropic_api_key: str = "",
        deep_think_model: str = "claude-sonnet-4-20250514",
        quick_think_model: str = "claude-sonnet-4-20250514",
        max_debate_rounds: int = 2,
        confidence_threshold: float = 0.5,
        max_tp_adjustment: float = 5.5,
    ) -> None:
        self._api_key = anthropic_api_key
        self._deep_think = deep_think_model
        self._quick_think = quick_think_model
        self._debate_rounds = max_debate_rounds
        self._confidence_threshold = confidence_threshold
        self._max_tp = max_tp_adjustment
        self._call_count: int = 0
        self._total_latency_ms: float = 0.0

    @property
    def stats(self) -> dict[str, Any]:
        avg = self._total_latency_ms / self._call_count if self._call_count else 0
        return {
            "total_calls": self._call_count,
            "avg_latency_ms": round(avg, 1),
            "deep_think_model": self._deep_think,
            "quick_think_model": self._quick_think,
        }

    async def analyze(self, symbol: str, date: str = "") -> dict[str, Any]:
        """Run full multi-agent analysis for a symbol.

        Args:
            symbol: Trading symbol (e.g. "BTC", "BTC-USD")
            date: Analysis date (YYYY-MM-DD), defaults to today

        Returns:
            Decision dict with keys: approved, confidence, reason, direction,
            tp_adjustment, risk_level, action, entry_price, target_price,
            stop_loss, warning
        """
        import asyncio
        import time

        t0 = time.monotonic()
        self._call_count += 1

        # If no API key is configured, return fallback
        if not self._api_key:
            logger.warning("trading_agents_no_api_key | anthropic_api_key not set")
            return self._fallback_decision("No API key configured for TradingAgents")

        try:
            # Build config
            config = self._build_config()

            # Initialize TradingAgents graph
            from tradingagents.graph.trading_graph import TradingAgentsGraph

            ta = TradingAgentsGraph(**config.model_dump())

            # Set the date
            trade_date = date or datetime.date.today().isoformat()

            # Clean symbol for TradingAgents (it expects company name / ticker)
            ticker = symbol.replace("-USD", "").replace("USDT", "").split("/")[0]

            logger.info(
                "trading_agents_analyze | symbol=%s | ticker=%s | date=%s",
                symbol, ticker, trade_date,
            )

            # Run full multi-agent analysis in thread executor (blocks)
            loop = asyncio.get_running_loop()
            _state, recommendation = await loop.run_in_executor(
                None, lambda: ta.propagate(ticker, trade_date)
            )

            latency = (time.monotonic() - t0) * 1000
            self._total_latency_ms += latency

            if recommendation is None:
                return self._fallback_decision("TradingAgents returned no recommendation")

            logger.info(
                "trading_agents_result | signal=%s | confidence=%.2f | rationale=%.60s | latency=%.0fms",
                recommendation.signal,
                recommendation.confidence,
                recommendation.rationale,
                latency,
            )

            # Convert to SVTR decision format
            return self._recommendation_to_decision(recommendation)

        except Exception as e:
            latency = (time.monotonic() - t0) * 1000
            self._total_latency_ms += latency
            logger.error("trading_agents_error | %s | latency=%.0fms", e, latency)
            return self._fallback_decision(f"TradingAgents error: {e}")

    def _build_config(self) -> Any:
        """Build TradingAgentsConfig from settings."""
        from tradingagents.config import TradingAgentsConfig

        return TradingAgentsConfig(
            llm_provider="anthropic",
            deep_think_llm=self._deep_think,
            quick_think_llm=self._quick_think,
            reasoning_effort="medium",
            response_language="en-US",
            max_debate_rounds=self._debate_rounds,
            max_risk_discuss_rounds=self._debate_rounds,
            max_recur_limit=50,
            results_dir=settings.data_dir / "trading_agents_results",
        )

    def _recommendation_to_decision(self, rec: Any | None) -> dict[str, Any]:
        """Convert TradingAgents TradeRecommendation to SVTR decision dict."""
        if rec is None:
            return self._fallback_decision("No recommendation provided")

        try:
            signal = str(getattr(rec, "signal", "HOLD")).upper()
            confidence = float(getattr(rec, "confidence", 0.0))
            rationale = str(getattr(rec, "rationale", ""))
            size = float(getattr(rec, "size_fraction", 0.0))
            entry = getattr(rec, "entry_reference_price", None)
            target = getattr(rec, "target_price", None)
            stop = getattr(rec, "stop_loss", None)
            warning = getattr(rec, "warning_message", None)
        except Exception as e:
            return self._fallback_decision(f"Error parsing recommendation: {e}")

        # Map signal → direction
        if signal == "BUY":
            direction = "long"
        elif signal == "SELL":
            direction = "short"
        else:
            direction = "hold"

        # Check confidence threshold
        if confidence < self._confidence_threshold:
            return {
                "approved": False,
                "confidence": self._scale_confidence(confidence),
                "reason": f"trading_agents_low_confidence: {confidence:.2f} < {self._confidence_threshold}",
                "direction": direction,
                "tp_adjustment": 0.0,
                "risk_level": "high",
                "action": "rejected",
                "entry_price": entry,
                "target_price": target,
                "stop_loss": stop,
                "warning": warning,
                "size_fraction": size,
            }

        # Calculate TP adjustment from target price
        tp_adj = self._calculate_tp_adjustment(direction, entry, target)

        # Determine risk level
        risk_level = self._determine_risk_level(confidence, signal)

        # Build reason
        reason_parts = [rationale] if rationale else []
        if warning:
            reason_parts.append(f"⚠️ {warning}")
        reason = " | ".join(reason_parts)

        return {
            "approved": True if direction != "hold" else False,
            "confidence": self._scale_confidence(confidence),
            "reason": reason if reason else "TradingAgents analysis completed",
            "direction": direction,
            "tp_adjustment": tp_adj,
            "risk_level": risk_level,
            "action": "approved",
            "entry_price": entry,
            "target_price": target,
            "stop_loss": stop,
            "warning": warning,
            "size_fraction": size,
        }

    def _fallback_decision(self, reason: str) -> dict[str, Any]:
        """Return safe fallback when TradingAgents is unavailable."""
        return {
            "approved": False,
            "confidence": 0,
            "reason": reason,
            "direction": "hold",
            "tp_adjustment": 0.0,
            "risk_level": "high",
            "action": "error",
            "entry_price": None,
            "target_price": None,
            "stop_loss": None,
            "warning": None,
            "size_fraction": 0.0,
        }

    @staticmethod
    def _scale_confidence(confidence: float) -> int:
        """Scale 0.0-1.0 confidence to 0-100 integer."""
        return min(100, max(0, int(confidence * 100)))

    @staticmethod
    def _determine_risk_level(confidence: float, signal: str) -> str:
        """Map confidence + signal to risk level."""
        if signal == "SELL":
            # SELL is inherently higher risk in a long-biased system
            if confidence >= 0.8:
                return "medium"
            return "high"
        # BUY / HOLD
        if confidence >= 0.8:
            return "low"
        if confidence >= 0.6:
            return "medium"
        return "high"

    def _calculate_tp_adjustment(
        self,
        direction: str,
        entry_price: float | None,
        target_price: float | None,
    ) -> float:
        """Calculate TP adjustment % from target vs entry price."""
        if entry_price is None or target_price is None or entry_price <= 0:
            return 0.0

        if direction == "long":
            pct = (target_price - entry_price) / entry_price * 100
        elif direction == "short":
            pct = (entry_price - target_price) / entry_price * 100
        else:
            return 0.0

        return min(self._max_tp, max(0.0, pct))
