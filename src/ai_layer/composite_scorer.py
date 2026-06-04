"""Composite Scorer — multi-factor trade decision scoring.

Combines: Technical Signal + Sentiment + AI + Market Context
into a single composite score with weighted factors.

This replaces the simple threshold-based approach with a nuanced
scoring system that considers multiple dimensions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScoreComponent:
    """Individual scoring component with weight and value."""

    name: str
    value: float  # -1.0 to +1.0 (normalized)
    weight: float  # 0.0 to 1.0
    raw_value: Any = None  # original un-normalized value
    reason: str = ""


@dataclass
class CompositeScore:
    """Final composite scoring result."""

    score: float = 0.0  # -1.0 to +1.0
    components: list[ScoreComponent] = field(default_factory=list)
    decision: str = "hold"  # "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"
    confidence: float = 0.0  # 0.0 to 1.0
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 3),
            "decision": self.decision,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "components": [
                {"name": c.name, "value": round(c.value, 3), "weight": c.weight, "reason": c.reason}
                for c in self.components
            ],
        }


class CompositeScorer:
    """Multi-factor composite scoring engine.

    Scoring pipeline:
    1. Normalize each factor to [-1.0, +1.0]
    2. Apply weights
    3. Sum weighted scores
    4. Apply decision thresholds

    Default weights (configurable):
    - Technical signal: 35%
    - Sentiment: 20%
    - AI assessment: 25%
    - Market context: 20%
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or {
            "technical": 0.35,
            "sentiment": 0.20,
            "ai": 0.25,
            "market": 0.20,
        }
        # Decision thresholds
        self.strong_threshold = 0.6
        self.buy_threshold = 0.3
        self.sell_threshold = -0.3
        self.strong_sell_threshold = -0.6

    def score(
        self,
        *,
        technical_score: float,
        technical_max: float = 13.5,
        sentiment_score: float = 0.0,
        sentiment_confidence: float = 0.5,
        ai_approved: bool | None = None,
        ai_confidence: int = 0,
        ai_risk_level: str = "medium",
        funding_rate: float = 0.0,
        funding_extreme: bool = False,
        volume_ratio: float = 1.0,
        fear_greed: int = 50,
    ) -> CompositeScore:
        """Calculate composite score from all factors.

        Args:
            technical_score: Raw signal score (0 to technical_max)
            technical_max: Maximum possible technical score
            sentiment_score: Sentiment score (-1.0 to +1.0)
            sentiment_confidence: How confident in sentiment (0.0 to 1.0)
            ai_approved: AI's approval decision (None if AI disabled)
            ai_confidence: AI confidence (0-100)
            ai_risk_level: AI risk assessment
            funding_rate: Current funding rate
            funding_extreme: Whether funding is extreme
            volume_ratio: Current/average volume ratio
            fear_greed: Fear & Greed index (0-100)
        """
        components: list[ScoreComponent] = []

        # ── 1. Technical Score ──────────────────────────────────
        tech_normalized = (technical_score / technical_max) * 2.0 - 1.0  # map to [-1, 1]
        tech_normalized = max(-1.0, min(1.0, tech_normalized))
        components.append(ScoreComponent(
            name="technical",
            value=tech_normalized,
            weight=self.weights["technical"],
            raw_value=technical_score,
            reason=f"{technical_score:.1f}/{technical_max}",
        ))

        # ── 2. Sentiment Score ──────────────────────────────────
        # Weight sentiment by its confidence
        sentiment_weighted = sentiment_score * sentiment_confidence
        components.append(ScoreComponent(
            name="sentiment",
            value=sentiment_weighted,
            weight=self.weights["sentiment"],
            raw_value=sentiment_score,
            reason=f"score={sentiment_score:.2f}, conf={sentiment_confidence:.2f}",
        ))

        # ── 3. AI Assessment ────────────────────────────────────
        if ai_approved is not None:
            ai_value = 1.0 if ai_approved else -1.0
            # Scale by confidence
            ai_conf_norm = ai_confidence / 100.0
            ai_value *= ai_conf_norm

            # Risk level adjustment
            risk_penalty = {"low": 0.0, "medium": -0.1, "high": -0.3}.get(
                ai_risk_level, -0.2
            )
            ai_value += risk_penalty
            ai_value = max(-1.0, min(1.0, ai_value))

            components.append(ScoreComponent(
                name="ai",
                value=ai_value,
                weight=self.weights["ai"],
                raw_value={"approved": ai_approved, "confidence": ai_confidence},
                reason=f"approved={ai_approved}, conf={ai_confidence}, risk={ai_risk_level}",
            ))
        else:
            # AI disabled — redistribute weight to technical
            components.append(ScoreComponent(
                name="ai",
                value=0.0,
                weight=0.0,
                reason="AI disabled",
            ))

        # ── 4. Market Context ───────────────────────────────────
        market_value = 0.0
        market_reasons: list[str] = []

        # Funding rate signal
        if funding_extreme:
            # Extreme funding = strong contrarian signal
            market_value -= 0.4 * (1 if funding_rate > 0 else -1)
            market_reasons.append(f"extreme funding ({funding_rate:.4f})")

        # Volume confirmation
        if volume_ratio > 1.5:
            market_value += 0.3
            market_reasons.append(f"high volume ({volume_ratio:.1f}x)")
        elif volume_ratio < 0.5:
            market_value -= 0.3
            market_reasons.append(f"low volume ({volume_ratio:.1f}x)")

        # Fear & Greed contrarian signal
        fg_norm = (fear_greed - 50) / 50  # -1 to +1
        if abs(fg_norm) > 0.6:
            # Extreme values → contrarian
            market_value -= fg_norm * 0.2
            market_reasons.append(f"extreme F&G ({fear_greed})")

        market_value = max(-1.0, min(1.0, market_value))
        components.append(ScoreComponent(
            name="market",
            value=market_value,
            weight=self.weights["market"],
            raw_value={"funding": funding_rate, "volume_ratio": volume_ratio, "fg": fear_greed},
            reason="; ".join(market_reasons) if market_reasons else "neutral",
        ))

        # ── Calculate composite score ───────────────────────────
        total_weight = sum(c.weight for c in components)
        if total_weight > 0:
            composite = sum(c.value * c.weight for c in components) / total_weight
        else:
            composite = 0.0

        composite = max(-1.0, min(1.0, composite))

        # ── Determine decision ──────────────────────────────────
        if composite >= self.strong_threshold:
            decision = "strong_buy"
        elif composite >= self.buy_threshold:
            decision = "buy"
        elif composite <= self.strong_sell_threshold:
            decision = "strong_sell"
        elif composite <= self.sell_threshold:
            decision = "sell"
        else:
            decision = "hold"

        # ── Calculate confidence ────────────────────────────────
        # Confidence based on component agreement
        if len(components) >= 2:
            signs = [1 if c.value > 0 else -1 if c.value < 0 else 0 for c in components if c.weight > 0]
            if signs:
                agreement = abs(sum(signs)) / len(signs)
            else:
                agreement = 0.0
        else:
            agreement = 0.5
        confidence = abs(composite) * agreement

        # ── Build reasoning ─────────────────────────────────────
        reasons = [f"{c.name}: {c.reason}" for c in components if c.weight > 0]
        reasoning = " | ".join(reasons)

        result = CompositeScore(
            score=round(composite, 3),
            components=components,
            decision=decision,
            confidence=round(confidence, 3),
            reasoning=reasoning,
        )

        logger.info(
            "composite_score=%.3f | decision=%s | confidence=%.3f | %s",
            result.score,
            result.decision,
            result.confidence,
            reasoning,
        )

        return result
