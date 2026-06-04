"""Decision Engine — multi-factor trade decision pipeline.

Combines: Technical Signal + Sentiment + AI → Final Decision
"""

from __future__ import annotations

import logging
from typing import Any

from src.config import settings
from src.decision.risk import RiskManager
from src.decision.position import PositionManager, ExitType
from src.signal_engine.scoring import calculate_signal_strength, SignalResult, SignalWeights
from src.signal_engine.dynamic_tp import calculate_dynamic_tp
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
    ) -> None:
        self.risk = risk_manager
        self.positions = position_manager
        self.ai = ai_client
        self.exchange = exchange_client
        self.telegram = telegram

    async def evaluate_alert(self, payload: TVAlertPayload) -> dict[str, Any]:
        """Full evaluation pipeline for an incoming TradingView alert.

        Steps:
        1. Risk check (circuit breaker, daily limits)
        2. Signal quality check (min score threshold)
        3. AI evaluation (if enabled)
        4. Position sizing
        5. Order execution
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

        # ── Step 2: Signal Quality ────────────────────────────────
        if payload.signal_score < settings.min_signal_score:
            result["reason"] = (
                f"score_too_low: {payload.signal_score:.1f} < {settings.min_signal_score}"
            )
            logger.info("trade_rejected_low_score | %.1f", payload.signal_score)
            return result

        # ── Step 3: AI Evaluation ─────────────────────────────────
        ai_decision = None
        risk_level = "medium"

        if settings.ai_enabled and self.ai:
            signal_data = {
                "symbol": payload.symbol,
                "direction": payload.direction.value,
                "score": payload.signal_score,
                "adx": 0,
                "di_plus": 0,
                "di_minus": 0,
                "rsi": 50,
                "tp_distance": payload.tp_distance,
                "vwap_score": 0,
                "macd_score": 0,
            }
            market_context = {
                "funding_rate": 0,
                "oi_change": 0,
                "fear_greed": 50,
                "volume_change": 0,
            }
            sentiment_data = {
                "news_count": 0,
                "pos_neg_ratio": 0.5,
                "social_mentions": 0,
                "sentiment_score": 0,
            }

            ai_decision = await self.ai.evaluate_signal(
                signal_data, market_context, sentiment_data
            )

            if not ai_decision.approved:
                result["reason"] = f"ai_rejected: {ai_decision.reason}"
                logger.info("trade_rejected_ai | %s", ai_decision.reason)
                return result

            risk_level = ai_decision.risk_level
            result["ai_confidence"] = ai_decision.confidence
            result["ai_reason"] = ai_decision.reason

        # ── Step 4: Position Sizing ───────────────────────────────
        equity = 100_000.0  # TODO: fetch from exchange
        position_pct = self.risk.calculate_position_size(
            equity, payload.signal_score, risk_level
        )
        position_value = equity * position_pct / 100.0
        quantity = position_value / payload.price if payload.price > 0 else 0

        result["position_pct"] = position_pct
        result["quantity"] = round(quantity, 6)

        # ── Step 5: TP/SL Calculation ─────────────────────────────
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

        # ── Step 6: Execute ───────────────────────────────────────
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
