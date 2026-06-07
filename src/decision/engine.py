"""Decision Engine — multi-factor trade decision pipeline.

Combines: Technical Signal + Sentiment + Market Data + AI → Final Decision
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from src.config import settings
from src.decision.risk import RiskManager
from src.decision.position import PositionManager, ExitType
from src.signal_engine.scoring import calculate_signal_strength, SignalResult, SignalWeights
from src.signal_engine.dynamic_tp import calculate_dynamic_tp
from src.sentiment.market_data import fetch_market_context
from src.sentiment.sentiment_pipeline import SentimentCollector
from src.ai_layer.composite_scorer import CompositeScorer
from src.ai_layer.decision_logger import AIDecisionLogger
from src.ai_layer.trading_agents import TradingAgentsDecisionClient
from src.webhook.models import TVAlertPayload

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Orchestrates the full signal → decision → action pipeline."""

    def __init__(
        self,
        risk_manager: RiskManager,
        position_manager: PositionManager,
        ai_client: Any = None,  # ClaudeClient
        exchange_client: Any = None,  # ExchangeClient
        telegram: Any = None,  # TelegramNotifier
        trading_agents_client: TradingAgentsDecisionClient | None = None,
    ) -> None:
        self.risk = risk_manager
        self.positions = position_manager
        self.ai = ai_client
        self.exchange = exchange_client
        self.telegram = telegram
        self._sentiment = SentimentCollector(ai_client=ai_client)
        self._scorer = CompositeScorer()
        self._decision_log = AIDecisionLogger()
        self._ta = trading_agents_client

    async def evaluate_alert(self, payload: TVAlertPayload) -> dict[str, Any]:
        """Full evaluation pipeline for an incoming TradingView alert.

        Steps:
        1. Risk check (circuit breaker, daily limits)
        2. Signal quality check (min score threshold)
        3. Fetch real market data + sentiment
        4. AI evaluation (if enabled)
        5. Position sizing
        6. TP/SL calculation
        7. Order execution
        """
        result: dict[str, Any] = {
            "action": "none",
            "reason": "",
            "score": payload.signal_score,
        }

        # ── Step 1: Risk Check ────────────────────────────────────
        can_trade, risk_reason = self.risk.can_trade()
        if not can_trade:
            result["reason"] = f"risk_blocked: {risk_reason}"
            logger.warning("trade_blocked_risk | %s", risk_reason)
            return result

        if self.positions.has_position_for(payload.symbol):
            result["reason"] = f"position_already_active: {payload.symbol}"
            logger.info("trade_rejected_duplicate_position | %s", payload.symbol)
            return result

        # ── Step 2: Signal Quality ────────────────────────────────
        if payload.signal_score < settings.min_signal_score:
            result["reason"] = (
                f"score_too_low: {payload.signal_score:.1f} < {settings.min_signal_score}"
            )
            logger.info("trade_rejected_low_score | %.1f", payload.signal_score)
            return result

        # ── Step 3: Fetch Real Market Data + Sentiment ────────────
        market_context: dict[str, Any] = {
            "funding_rate": 0,
            "oi_change": 0,
            "fear_greed": 50,
            "volume_change": 0,
        }
        sentiment_result = None

        if settings.sentiment_enabled:
            try:
                # Fetch sentiment (news + fear & greed + social)
                sentiment_result = await self._sentiment.collect(
                    coin=payload.symbol.split("/")[0] if "/" in payload.symbol else payload.symbol.replace("USDT", "")
                )
            except Exception as e:
                logger.warning("sentiment_fetch_error | %s", e)

        if self.exchange:
            try:
                # Fetch real market context (funding rate, OI, volume)
                market_context = await fetch_market_context(
                    self.exchange, payload.symbol
                )
            except Exception as e:
                logger.warning("market_context_fetch_error | %s", e)

        # Enrich sentiment data for AI prompt
        sentiment_data: dict[str, Any] = {
            "news_count": sentiment_result.news_count if sentiment_result else 0,
            "pos_neg_ratio": sentiment_result.pos_neg_ratio if sentiment_result else 0.5,
            "social_mentions": 0,
            "sentiment_score": sentiment_result.score if sentiment_result else 0,
        }        # ── Step 4: AI Evaluation ─────────────────────────────────
        ai_decision = None
        risk_level = "medium"

        if settings.ai_enabled and self.ai:
            signal_data = {
                "symbol": payload.symbol,
                "direction": payload.direction.value,
                "score": payload.signal_score,
                "adx": 0,  # TODO: extract from webhook payload
                "di_plus": 0,
                "di_minus": 0,
                "rsi": 50,
                "tp_distance": payload.tp_distance,
                "vwap_score": 0,
                "macd_score": 0,
            }

            ai_decision = await self.ai.evaluate_signal(
                signal_data, market_context, sentiment_data
            )

            if not ai_decision.approved:
                result["reason"] = f"ai_rejected: {ai_decision.reason}"
                logger.info("trade_rejected_ai | %s", ai_decision.reason)

                # Log the rejection
                self._decision_log.log_signal_eval(
                    symbol=payload.symbol,
                    direction=payload.direction.value,
                    signal_score=payload.signal_score,
                    approved=False,
                    ai_confidence=ai_decision.confidence,
                    ai_risk_level=ai_decision.risk_level,
                    ai_reason=ai_decision.reason,
                    tp_adjustment=ai_decision.tp_adjustment,
                    funding_rate=market_context.get("funding_rate", 0),
                    fear_greed=market_context.get("fear_greed", 50),
                    volume_ratio=market_context.get("volume_ratio", 1.0),
                    sentiment_score=sentiment_data.get("sentiment_score", 0),
                    latency_ms=ai_decision.latency_ms,
                    model=ai_decision.model,
                )
                return result

            risk_level = ai_decision.risk_level
            result["ai_confidence"] = ai_decision.confidence
            result["ai_reason"] = ai_decision.reason

        # ── Step 4b: TradingAgents Multi-Agent Evaluation ────────
        ta_decision = None
        if self._ta and settings.anthropic_api_key:
            try:
                coin = (
                    payload.symbol.split("/")[0]
                    if "/" in payload.symbol
                    else payload.symbol.replace("USDT", "").replace("USD", "")
                )
                ta_decision = await self._ta.analyze(
                    symbol=coin,
                    date=datetime.date.today().isoformat(),
                )
                logger.info(
                    "trading_agents_decision | symbol=%s | approved=%s | confidence=%d | dir=%s",
                    coin,
                    ta_decision.get("approved"),
                    ta_decision.get("confidence", 0),
                    ta_decision.get("direction", "?"),
                )

                # TradingAgents rejection can override AI approval
                if not ta_decision.get("approved"):
                    result["reason"] = f"trading_agents_rejected: {ta_decision.get('reason', '')}"
                    logger.info("trade_rejected_ta | %s", ta_decision.get("reason"))
                    self._decision_log.log_signal_eval(
                        symbol=payload.symbol,
                        direction=payload.direction.value,
                        signal_score=payload.signal_score,
                        approved=False,
                        ai_confidence=ta_decision.get("confidence", 0),
                        ai_risk_level=ta_decision.get("risk_level", "high"),
                        ai_reason=ta_decision.get("reason", "TradingAgents rejected"),
                        tp_adjustment=ta_decision.get("tp_adjustment", 0.0),
                        funding_rate=market_context.get("funding_rate", 0),
                        fear_greed=market_context.get("fear_greed", 50),
                        volume_ratio=market_context.get("volume_ratio", 1.0),
                        sentiment_score=sentiment_data.get("sentiment_score", 0),
                        latency_ms=0,
                        model="tradingagents",
                    )
                    return result

            except Exception as e:
                logger.warning("trading_agents_eval_error | %s", e)
                # Don't block trade if TradingAgents fails — log and continue

        # ── Step 4c: Composite Scoring ─────────────────────────
        composite = self._scorer.score(
            technical_score=payload.signal_score,
            sentiment_score=sentiment_result.score if sentiment_result else 0.0,
            sentiment_confidence=sentiment_result.confidence if sentiment_result else 0.5,
            ai_approved=ai_decision.approved if ai_decision else None,
            ai_confidence=ai_decision.confidence if ai_decision else 0,
            ai_risk_level=risk_level,
            funding_rate=market_context.get("funding_rate", 0),
            funding_extreme=market_context.get("funding_is_extreme", False),
            volume_ratio=market_context.get("volume_ratio", 1.0),
            fear_greed=market_context.get("fear_greed", 50),
        )
        result["composite_score"] = composite.score
        result["composite_decision"] = composite.decision

        # Log the approved evaluation
        self._decision_log.log_signal_eval(
            symbol=payload.symbol,
            direction=payload.direction.value,
            signal_score=payload.signal_score,
            approved=True,
            ai_confidence=ai_decision.confidence if ai_decision else 0,
            ai_risk_level=risk_level,
            ai_reason=ai_decision.reason if ai_decision else "AI disabled",
            tp_adjustment=ai_decision.tp_adjustment if ai_decision else 0.0,
            funding_rate=market_context.get("funding_rate", 0),
            fear_greed=market_context.get("fear_greed", 50),
            volume_ratio=market_context.get("volume_ratio", 1.0),
            sentiment_score=sentiment_data.get("sentiment_score", 0),
            latency_ms=ai_decision.latency_ms if ai_decision else 0,
            model=ai_decision.model if ai_decision else "",
            composite_score=composite.score,
            composite_decision=composite.decision,
        )

        # Attach full context to result for logging/debugging
        result["market_context"] = market_context
        result["sentiment_score"] = sentiment_result.score if sentiment_result else 0.0

        # ── Step 5: Position Sizing ───────────────────────────────
        equity = 100_000.0  # TODO: fetch from exchange balance
        position_pct = self.risk.calculate_position_size(
            equity, payload.signal_score, risk_level
        )
        position_value = equity * position_pct / 100.0
        quantity = position_value / payload.price if payload.price > 0 else 0

        result["position_pct"] = position_pct
        result["quantity"] = round(quantity, 6)

        current_exposure_pct = sum(
            position.entry_price * position.quantity
            for position in self.positions.active_positions
        ) / equity * 100
        portfolio_allowed, portfolio_reason = self.risk.can_open_position(
            active_count=len(self.positions.active_positions),
            current_exposure_pct=current_exposure_pct,
            new_exposure_pct=position_pct,
            max_positions=settings.max_active_positions,
            max_exposure_pct=settings.max_portfolio_exposure_pct,
        )
        if not portfolio_allowed:
            result["reason"] = f"risk_blocked: {portfolio_reason}"
            logger.warning("trade_blocked_portfolio | %s", portfolio_reason)
            return result

        # ── Step 6: TP/SL Calculation ─────────────────────────────
        tp_distance = payload.tp_distance
        if ai_decision and ai_decision.tp_adjustment:
            tp_distance += ai_decision.tp_adjustment
            tp_distance = max(settings.min_tp_distance, min(settings.max_tp_distance, tp_distance))

        if payload.direction.value == "long":
            stop_price = payload.price * (1 - settings.atr_multiplier * 0.02)
            max_loss_price = payload.price * (1 - settings.max_loss_pct / 100)
        else:
            stop_price = payload.price * (1 + settings.atr_multiplier * 0.02)
            max_loss_price = payload.price * (1 + settings.max_loss_pct / 100)

        # ── Step 7: Execute ───────────────────────────────────────
        if self.exchange:
            try:
                order = await self.exchange.place_market_order(
                    symbol=payload.symbol,
                    side=payload.direction.value,
                    quantity=quantity,
                )

                # Track position
                self.positions.open_position(
                    symbol=payload.symbol,
                    side=payload.direction.value,
                    entry_price=payload.price,
                    entry_score=payload.signal_score,
                    dynamic_tp=tp_distance,
                    quantity=quantity,
                    stop_price=stop_price,
                    max_loss_price=max_loss_price,
                )

                result["action"] = "order_placed"
                result["order_id"] = order.get("id", "")
                result["tp_distance"] = tp_distance

                # Telegram notification
                if self.telegram:
                    await self.telegram.send_entry_alert(
                        symbol=payload.symbol,
                        side=payload.direction.value,
                        price=payload.price,
                        score=payload.signal_score,
                        tp_distance=tp_distance,
                    )

            except Exception as e:
                logger.error("order_execution_error | %s", e)
                result["reason"] = f"execution_error: {e}"
                result["action"] = "failed"
        else:
            result["action"] = "simulated"
            result["reason"] = "no_exchange_client"
            logger.info(
                "simulated_trade | %s %s | qty=%.6f | tp=%.1f%%",
                payload.direction.value,
                payload.symbol,
                quantity,
                tp_distance,
            )

        return result
