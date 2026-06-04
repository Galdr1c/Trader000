"""Prompt templates for Claude AI signal evaluation."""

from __future__ import annotations


SIGNAL_EVALUATION_PROMPT = """\
You are an expert cryptocurrency trading analyst. Evaluate this trading signal.

═══ TECHNICAL SIGNAL ═══
Symbol: {symbol}
Direction: {direction}
Signal Score: {score}/13.5
ADX: {adx:.1f} (DI+: {di_plus:.1f}, DI-: {di_minus:.1f})
RSI: {rsi:.1f}
Dynamic TP Distance: {tp_distance:.2f}%
VWAP Score: {vwap_score:.2f}
MACD Score: {macd_score:.2f}

═══ MARKET CONTEXT ═══
Funding Rate: {funding_rate:.4f}%
Open Interest Change: {oi_change:.1f}%
Fear & Greed Index: {fear_greed}/100
24h Volume Change: {volume_change:.1f}%

═══ SENTIMENT ═══
Recent News Headlines: {news_count} articles in last 4 hours
Positive/Negative Ratio: {pos_neg_ratio:.2f}
Social Media Mentions: {social_mentions}
Sentiment Score: {sentiment_score:.2f} (-1=bearish, +1=bullish)

═══ TASK ═══
Based on all the above data, decide whether to APPROVE or REJECT this trade.

Consider:
1. Is the technical signal strong enough?
2. Does the market context support the direction?
3. Is the sentiment aligned?
4. Are there any red flags (extreme funding, negative sentiment)?

Return ONLY a JSON object (no markdown, no explanation outside JSON):
{{"approved": true/false, "confidence": 0-100, "reason": "brief explanation", "tp_adjustment": 0.0, "risk_level": "low/medium/high"}}
"""


def build_signal_evaluation_prompt(
    signal_data: dict,
    market_context: dict,
    sentiment_data: dict,
) -> str:
    """Build the evaluation prompt from signal + market + sentiment data."""
    return SIGNAL_EVALUATION_PROMPT.format(
        symbol=signal_data.get("symbol", "UNKNOWN"),
        direction=signal_data.get("direction", "long"),
        score=signal_data.get("score", 0),
        adx=signal_data.get("adx", 0),
        di_plus=signal_data.get("di_plus", 0),
        di_minus=signal_data.get("di_minus", 0),
        rsi=signal_data.get("rsi", 50),
        tp_distance=signal_data.get("tp_distance", 5.0),
        vwap_score=signal_data.get("vwap_score", 0),
        macd_score=signal_data.get("macd_score", 0),
        funding_rate=market_context.get("funding_rate", 0),
        oi_change=market_context.get("oi_change", 0),
        fear_greed=market_context.get("fear_greed", 50),
        volume_change=market_context.get("volume_change", 0),
        news_count=sentiment_data.get("news_count", 0),
        pos_neg_ratio=sentiment_data.get("pos_neg_ratio", 0.5),
        social_mentions=sentiment_data.get("social_mentions", 0),
        sentiment_score=sentiment_data.get("sentiment_score", 0),
    )
