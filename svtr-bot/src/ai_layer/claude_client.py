"""Claude API client for AI-powered signal evaluation.

Uses Anthropic SDK with structured JSON output for trading decisions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

from src.config import settings
from src.ai_layer.prompts import build_signal_evaluation_prompt

logger = logging.getLogger(__name__)


@dataclass
class AIDecision:
    approved: bool
    confidence: int  # 0-100
    reason: str
    tp_adjustment: float  # percentage points to adjust TP
    risk_level: str  # "low", "medium", "high"


class ClaudeClient:
    """Async wrapper around the Anthropic Claude API."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model
        self._max_tokens = settings.ai_max_tokens

    async def evaluate_signal(
        self,
        signal_data: dict,
        market_context: dict,
        sentiment_data: dict,
    ) -> AIDecision:
        """Evaluate a trading signal using Claude.

        Returns an AIDecision with approval, confidence, and adjustments.
        """
        try:
            prompt = build_signal_evaluation_prompt(
                signal_data, market_context, sentiment_data
            )

            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text
            # Extract JSON from response (may be wrapped in markdown)
            json_str = text
            if "```" in text:
                json_str = text.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
                json_str = json_str.strip()

            data = json.loads(json_str)

            return AIDecision(
                approved=data.get("approved", False),
                confidence=min(100, max(0, data.get("confidence", 0))),
                reason=data.get("reason", "No reason provided"),
                tp_adjustment=data.get("tp_adjustment", 0.0),
                risk_level=data.get("risk_level", "medium"),
            )

        except Exception as e:
            logger.error("claude_api_error | %s", e)
            # Default: reject on error (fail-safe)
            return AIDecision(
                approved=False,
                confidence=0,
                reason=f"AI evaluation failed: {e}",
                tp_adjustment=0.0,
                risk_level="high",
            )

    async def analyze_sentiment(
        self, news: list[dict], tweets: str, reddit: str, fear_greed: int, coin: str
    ) -> float:
        """Analyze combined sentiment data. Returns score -1.0 to +1.0."""
        try:
            prompt = f"""Analyze the market sentiment for {coin} based on:

News articles: {json.dumps(news[:5], ensure_ascii=False)[:1500]}
Twitter/X mentions: {tweets[:1000]}
Reddit discussion: {reddit[:1000]}
Fear & Greed Index: {fear_greed}/100

Return ONLY a JSON object: {{"score": <float from -1.0 to 1.0>, "reason": "<brief explanation>"}}
"""
            response = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            return max(-1.0, min(1.0, data.get("score", 0.0)))

        except Exception as e:
            logger.error("sentiment_analysis_error | %s", e)
            return 0.0  # Neutral on error
