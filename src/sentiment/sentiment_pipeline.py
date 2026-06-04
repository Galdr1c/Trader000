"""Composite Sentiment Pipeline — orchestrates all sentiment data sources.

Gathers: news (RSS + CryptoPanic), social media (Agent-Reach),
Fear & Greed Index, and produces a unified sentiment score (-1.0 to +1.0)
for the AI evaluation layer.

Usage:
    from src.sentiment.sentiment_pipeline import SentimentCollector

    collector = SentimentCollector(ai_client=claude_client)
    result = await collector.collect("BTC")
    # result = {"score": 0.65, "reason": "...", "sources": {...}}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import settings
from src.sentiment.news import fetch_crypto_news
from src.sentiment.fear_greed import fetch_fear_greed
from src.sentiment.social import get_twitter_sentiment, get_reddit_sentiment

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Aggregated sentiment analysis result."""

    score: float = 0.0  # -1.0 (bearish) to +1.0 (bullish)
    confidence: float = 0.5  # 0.0 to 1.0
    reason: str = ""
    sources: dict[str, Any] = field(default_factory=dict)
    news_count: int = 0
    pos_neg_ratio: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "confidence": self.confidence,
            "reason": self.reason,
            "news_count": self.news_count,
            "pos_neg_ratio": self.pos_neg_ratio,
            "sources": self.sources,
        }


class SentimentCollector:
    """Orchestrates sentiment data collection from all sources.

    Produces a unified SentimentResult that can be fed directly
    into the AI evaluation layer.
    """

    def __init__(self, ai_client: Any = None) -> None:
        self._ai = ai_client

    async def collect(self, coin: str = "BTC") -> SentimentResult:
        """Collect sentiment from all sources and produce unified score.

        Steps:
        1. Fetch news (RSS + CryptoPanic) in parallel with Fear & Greed
        2. Fetch social media sentiment (Twitter + Reddit) — may be no-op if CLIs missing
        3. Combine all data and compute composite score (rule-based + optional AI)
        """
        import asyncio

        # ── Step 1: Parallel fetch news + fear_greed ──────────────
        news_task = fetch_crypto_news(coin=coin, hours=4)
        fg_task = fetch_fear_greed()
        twitter_task = get_twitter_sentiment(coin)
        reddit_task = get_reddit_sentiment(coin)

        news, fear_greed, twitter_text, reddit_text = await asyncio.gather(
            news_task, fg_task, twitter_task, reddit_task
        )

        # ── Step 2: Basic sentiment metrics ───────────────────────
        news_count = len(news)
        pos_count = sum(
            1 for n in news
            if _is_positive_news(n.get("title", "") + n.get("summary", ""))
        )
        neg_count = sum(
            1 for n in news
            if _is_negative_news(n.get("title", "") + n.get("summary", ""))
        )
        pos_neg_ratio = pos_count / max(1, pos_count + neg_count)

        # ── Step 3: Rule-based composite score ────────────────────
        rule_score = self._compute_rule_based_score(
            fear_greed=fear_greed,
            pos_neg_ratio=pos_neg_ratio,
            news_count=news_count,
            has_social=bool(twitter_text and "[not available" not in twitter_text.lower()),
        )

        # ── Step 4: AI-enhanced score (if available) ──────────────
        if self._ai and settings.ai_enabled and news_count > 0:
            try:
                ai_result = await self._ai.analyze_sentiment(
                    news=news,
                    tweets=twitter_text,
                    reddit=reddit_text,
                    fear_greed=fear_greed,
                    coin=coin,
                )
                # Handle both SentimentDecision object and plain float
                if hasattr(ai_result, "score"):
                    ai_score = ai_result.score
                    ai_confidence = ai_result.confidence
                else:
                    ai_score = float(ai_result)
                    ai_confidence = 0.8
                # Weighted average: 60% AI, 40% rule-based
                final_score = 0.6 * ai_score + 0.4 * rule_score
                reason = f"AI+rule composite: AI={ai_score:.2f}, rule={rule_score:.2f}"
                confidence = 0.6 * ai_confidence + 0.4 * 0.5
            except Exception as e:
                logger.warning("ai_sentiment_error | %s", e)
                final_score = rule_score
                reason = f"Rule-based only (AI error): {rule_score:.2f}"
                confidence = 0.5
        else:
            final_score = rule_score
            reason = f"Rule-based: fear_greed={fear_greed}, pos_ratio={pos_neg_ratio:.2f}"
            confidence = 0.5

        # Clamp to [-1.0, 1.0]
        final_score = max(-1.0, min(1.0, final_score))

        result = SentimentResult(
            score=round(final_score, 3),
            confidence=confidence,
            reason=reason,
            news_count=news_count,
            pos_neg_ratio=round(pos_neg_ratio, 2),
            sources={
                "fear_greed": fear_greed,
                "news_count": news_count,
                "twitter_available": bool(twitter_text and "not installed" not in twitter_text.lower()),
                "reddit_available": bool(reddit_text and "not installed" not in reddit_text.lower()),
            },
        )

        logger.info(
            "sentiment_collected | coin=%s | score=%.3f | confidence=%.2f | news=%d | fg=%d",
            coin,
            result.score,
            result.confidence,
            news_count,
            fear_greed,
        )

        return result

    @staticmethod
    def _compute_rule_based_score(
        fear_greed: int,
        pos_neg_ratio: float,
        news_count: int,
        has_social: bool,
    ) -> float:
        """Compute a rule-based sentiment score from raw metrics.

        Fear & Greed: 0-100 → mapped to sentiment
        pos_neg_ratio: 0.0-1.0 → directional bias
        """
        # Fear & Greed → sentiment score
        # Low F&G (fear) = contrarian bullish signal, High F&G (greed) = bearish caution
        # But for trend-following, high F&G = bullish confirmation
        fg_normalized = (fear_greed - 50) / 50  # -1.0 to +1.0
        fg_score = fg_normalized * 0.4  # Weight: 40%

        # News sentiment ratio → directional
        news_score = (pos_neg_ratio - 0.5) * 2.0 * 0.35  # Weight: 35%

        # News volume factor — more news = more confident
        volume_factor = min(1.0, news_count / 10) * 0.15  # Weight: 15%

        # Social media presence bonus
        social_bonus = 0.10 if has_social else 0.0  # Weight: 10%

        score = fg_score + news_score + (volume_factor * (1 if pos_neg_ratio > 0.5 else -1)) + social_bonus

        return max(-1.0, min(1.0, score))


# ── Simple keyword-based sentiment helpers ────────────────────────

_POSITIVE_KEYWORDS = frozenset([
    "surge", "rally", "bull", "bullish", "moon", "pump", "gain", "profit",
    "breakout", "record", "high", "adoption", "approval", "etf approved",
    "partnership", "upgrade", "milestone", "accumulation", "institutional",
    "green", "up", "recovery", "boom", "launch",
])

_NEGATIVE_KEYWORDS = frozenset([
    "crash", "dump", "bear", "bearish", "hack", "exploit", "scam",
    "ban", "regulation", "lawsuit", "sec", "fraud", "collapse",
    "decline", "loss", "plunge", "sell-off", "liquidation", "bankrupt",
    "warning", "risk", "down", "red", "fear", "panic",
])


def _is_positive_news(text: str) -> bool:
    """Quick keyword check for positive news."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _POSITIVE_KEYWORDS)


def _is_negative_news(text: str) -> bool:
    """Quick keyword check for negative news."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _NEGATIVE_KEYWORDS)
