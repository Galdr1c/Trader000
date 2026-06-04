"""Prompt templates for Claude AI signal evaluation.

Phase 3: Enhanced prompts with system context, few-shot examples,
volatility regime awareness, and structured output schemas.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════
# System Prompt (applied to all Claude calls)
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are an expert cryptocurrency trading analyst working for an algorithmic trading system.
You evaluate incoming trading signals against multiple data sources and provide structured decisions.

CORE PRINCIPLES:
1. Capital preservation is the #1 priority. When in doubt, REJECT.
2. A signal with high technical score but bad market context is a TRAP.
3. Extreme funding rates (>0.1%) and extreme Fear & Greed (>80 or <20) are red flags.
4. Volume confirmation is essential — high price + low volume = weak move.
5. News sentiment that contradicts the signal direction should override technicals.

OUTPUT RULES:
- Return ONLY valid JSON. No markdown, no explanation outside JSON.
- confidence must be an integer 0-100.
- tp_adjustment is in percentage points (e.g., -1.0 means reduce TP by 1%).
- risk_level must be exactly "low", "medium", or "high"."""


# ═══════════════════════════════════════════════════════════════════════
# Signal Evaluation Prompt (Phase 3 — enhanced)
# ═══════════════════════════════════════════════════════════════════════

SIGNAL_EVALUATION_PROMPT = """\
Analyze this trading signal for {symbol} and decide whether to APPROVE or REJECT.

═══ TECHNICAL SIGNAL ═══
Direction: {direction}
Signal Score: {score}/13.5
ADX: {adx:.1f} (DI+: {di_plus:.1f}, DI-: {di_minus:.1f})
RSI: {rsi:.1f}
Dynamic TP Distance: {tp_distance:.2f}%
VWAP Score: {vwap_score:.2f}
MACD Score: {macd_score:.2f}

═══ MARKET CONTEXT ═══
Funding Rate: {funding_rate:.4f}% {funding_alert}
Open Interest: {oi_current:.0f} | Change: {oi_change:.1f}%
Volume Ratio: {volume_ratio:.2f}x avg {volume_label}
Fear & Greed: {fear_greed}/100 {fear_greed_label}

═══ SENTIMENT ═══
News: {news_count} articles (last 4h) | pos/neg ratio: {pos_neg_ratio:.2f}
Sentiment Score: {sentiment_score:.2f} (-1=bearish, +1=bullish)
Social: twitter={twitter_available}, reddit={reddit_available}

═══ VOLATILITY REGIME ═══
{volatility_context}

═══ TASK ═══
Evaluate this signal considering:

1. **Signal Quality**: Is the score strong enough? Is ADX confirming trend?
2. **Market Context**: Does funding/OI/volume support the direction?
3. **Sentiment Alignment**: Is news/social sentiment aligned with direction?
4. **Risk Flags**: Extreme funding? Low volume? Contradicting sentiment?
5. **Volatility**: Is the current regime appropriate for this trade?

DECISION MATRIX (guidelines, not rules):
- Score ≥ 10 + aligned sentiment + normal funding → APPROVE (high confidence)
- Score ≥ 8 + neutral sentiment + normal funding → APPROVE (medium confidence)
- Score ≥ 8 + contradicting sentiment → REJECT or APPROVE (low confidence)
- Any extreme funding + any score → REJECT
- Low volume (< 1.0x avg) + score < 9 → REJECT

Return ONLY this JSON:
{{"approved": true/false, "confidence": 0-100, "reason": "brief explanation", "tp_adjustment": 0.0, "risk_level": "low/medium/high"}}"""


# ═══════════════════════════════════════════════════════════════════════
# Sentiment Analysis Prompt (Phase 3 — enhanced)
# ═══════════════════════════════════════════════════════════════════════

SENTIMENT_ANALYSIS_PROMPT = """\
Analyze the market sentiment for {coin} based on the following data.

═══ NEWS ARTICLES (last 4 hours) ═══
{news_text}

═══ SOCIAL MEDIA ═══
Twitter/X mentions:
{tweets}

Reddit discussion:
{reddit}

═══ FEAR & GREED INDEX ═══
Current: {fear_greed}/100
{fg_context}

═══ TASK ═══
Provide a sentiment assessment considering:

1. **Headline Tone**: Are news headlines mostly positive, negative, or mixed?
2. **Social Buzz**: Is there notable social media activity? Is it bullish or bearish?
3. **Fear/Greed Context**: Is the market in extreme fear (contrarian bullish) or extreme greed (caution)?
4. **Consistency**: Do news, social, and fear/greed agree?

Return ONLY this JSON:
{{"score": <float from -1.0 to +1.0>, "confidence": <float 0.0-1.0>, "reason": "<brief explanation>", "factors": ["factor1", "factor2"]}}"""


# ═══════════════════════════════════════════════════════════════════════
# Build functions
# ═══════════════════════════════════════════════════════════════════════


def _fear_greed_label(fg: int) -> str:
    """Human-readable Fear & Greed label."""
    if fg >= 80:
        return "⚠️ EXTREME GREED — caution"
    elif fg >= 60:
        return "(greedy)"
    elif fg >= 40:
        return "(neutral)"
    elif fg >= 20:
        return "(fearful)"
    else:
        return "⚠️ EXTREME FEAR — contrarian opportunity"


def _volatility_context(atr_pct: float = 0.0, adx: float = 0.0) -> str:
    """Describe the current volatility regime."""
    if atr_pct > 5.0:
        regime = "HIGH VOLATILITY — wide stops recommended, reduce position size"
    elif atr_pct > 2.0:
        regime = "NORMAL VOLATILITY — standard parameters appropriate"
    elif atr_pct > 0.5:
        regime = "LOW VOLATILITY — tighter stops, watch for breakout"
    else:
        regime = "VERY LOW VOLATILITY — possible accumulation phase, wait for expansion"

    trend = "STRONG TREND" if adx > 25 else "WEAK/RANGING" if adx > 15 else "NO TREND"
    return f"ATR-based: {regime}\nADX-based: {trend} (ADX={adx:.1f})"


def build_signal_evaluation_prompt(
    signal_data: dict,
    market_context: dict,
    sentiment_data: dict,
) -> str:
    """Build the enhanced evaluation prompt from signal + market + sentiment data."""
    fg = market_context.get("fear_greed", 50)
    adx = signal_data.get("adx", 0)

    return SIGNAL_EVALUATION_PROMPT.format(
        symbol=signal_data.get("symbol", "UNKNOWN"),
        direction=signal_data.get("direction", "long"),
        score=signal_data.get("score", 0),
        adx=adx,
        di_plus=signal_data.get("di_plus", 0),
        di_minus=signal_data.get("di_minus", 0),
        rsi=signal_data.get("rsi", 50),
        tp_distance=signal_data.get("tp_distance", 5.0),
        vwap_score=signal_data.get("vwap_score", 0),
        macd_score=signal_data.get("macd_score", 0),
        funding_rate=market_context.get("funding_rate", 0) * 100,
        funding_alert="EXTREME" if market_context.get("funding_is_extreme", False) else "",
        oi_current=market_context.get("open_interest", 0),
        oi_change=market_context.get("oi_change_pct", 0),
        volume_ratio=market_context.get("volume_ratio", 1.0),
        volume_label="HIGH" if market_context.get("is_high_volume", False) else "LOW",
        fear_greed=fg,
        fear_greed_label=_fear_greed_label(fg),
        news_count=sentiment_data.get("news_count", 0),
        pos_neg_ratio=sentiment_data.get("pos_neg_ratio", 0.5),
        sentiment_score=sentiment_data.get("sentiment_score", 0),
        twitter_available=sentiment_data.get("social_mentions", 0) > 0,
        reddit_available=sentiment_data.get("social_mentions", 0) > 0,
        volatility_context=_volatility_context(atr_pct=market_context.get("atr_pct", 0.0), adx=adx),
    )


def build_sentiment_analysis_prompt(
    news: list[dict],
    tweets: str,
    reddit: str,
    fear_greed: int,
    coin: str,
) -> str:
    """Build the enhanced sentiment analysis prompt."""
    # Format news for prompt
    news_lines = []
    for i, n in enumerate(news[:8], 1):
        title = n.get("title", "No title")
        summary = n.get("summary", "")[:100]
        news_lines.append(f"{i}. {title}\n   {summary}")
    news_text = "\n".join(news_lines) if news_lines else "No recent news available."

    # Fear & Greed context
    fg_ctx = _fear_greed_label(fear_greed)

    return SENTIMENT_ANALYSIS_PROMPT.format(
        coin=coin,
        news_text=news_text,
        tweets=tweets[:1500] if tweets else "No Twitter data available.",
        reddit=reddit[:1500] if reddit else "No Reddit data available.",
        fear_greed=fear_greed,
        fg_context=fg_ctx,
    )
