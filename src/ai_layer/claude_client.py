"""Claude API client for AI-powered signal evaluation.

Phase 3: Enhanced with system prompt, structured output parsing,
retry logic, and latency tracking.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from src.ai_layer.prompts import (
    SYSTEM_PROMPT,
    build_sentiment_analysis_prompt,
    build_signal_evaluation_prompt,
)
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AIDecision:
    """Structured AI trading decision."""

    approved: bool
    confidence: int  # 0-100
    reason: str
    tp_adjustment: float  # percentage points to adjust TP
    risk_level: str  # "low", "medium", "high"
    latency_ms: float = 0.0  # API call latency
    model: str = ""  # model used
    raw_response: str = ""  # for debugging


@dataclass
class SentimentDecision:
    """Structured AI sentiment analysis result."""

    score: float = 0.0  # -1.0 to +1.0
    confidence: float = 0.5  # 0.0 to 1.0
    reason: str = ""
    factors: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from Claude response (may be wrapped in markdown code blocks)."""
    json_str = text.strip()
    if "```" in json_str:
        parts = json_str.split("```")
        json_str = parts[1] if len(parts) > 1 else parts[0]
        if json_str.startswith("json"):
            json_str = json_str[4:]
        json_str = json_str.strip()
    return json.loads(json_str)


class ClaudeClient:
    """Async wrapper around the Anthropic Claude API.

    Phase 3 enhancements:
    - System prompt for consistent behavior
    - Latency tracking per call
    - Structured JSON output parsing
    - Retry on transient errors
    """

    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model
        self._max_tokens = settings.ai_max_tokens
        self._call_count: int = 0
        self._total_latency_ms: float = 0.0

    @property
    def stats(self) -> dict[str, Any]:
        """API usage statistics."""
        avg = self._total_latency_ms / self._call_count if self._call_count else 0
        return {
            "model": self._model,
            "total_calls": self._call_count,
            "avg_latency_ms": round(avg, 1),
            "total_latency_ms": round(self._total_latency_ms, 1),
        }

    async def evaluate_signal(
        self,
        signal_data: dict,
        market_context: dict,
        sentiment_data: dict,
    ) -> AIDecision:
        """Evaluate a trading signal using Claude.

        Returns an AIDecision with approval, confidence, and adjustments.
        """
        t0 = time.monotonic()

        try:
            prompt = build_signal_evaluation_prompt(
                signal_data, market_context, sentiment_data
            )

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            latency = (time.monotonic() - t0) * 1000
            self._call_count += 1
            self._total_latency_ms += latency

            text = response.content[0].text
            data = _parse_json_response(text)

            decision = AIDecision(
                approved=data.get("approved", False),
                confidence=min(100, max(0, data.get("confidence", 0))),
                reason=data.get("reason", "No reason provided"),
                tp_adjustment=data.get("tp_adjustment", 0.0),
                risk_level=data.get("risk_level", "medium"),
                latency_ms=round(latency, 1),
                model=self._model,
                raw_response=text,
            )

            logger.info(
                "ai_signal_eval | approved=%s | confidence=%d | risk=%s | latency=%.0fms",
                decision.approved,
                decision.confidence,
                decision.risk_level,
                decision.latency_ms,
            )
            return decision

        except Exception as e:
            latency = (time.monotonic() - t0) * 1000
            self._call_count += 1
            self._total_latency_ms += latency
            logger.error("claude_api_error | %s | latency=%.0fms", e, latency)
            return AIDecision(
                approved=False,
                confidence=0,
                reason=f"AI evaluation failed: {e}",
                tp_adjustment=0.0,
                risk_level="high",
                latency_ms=round(latency, 1),
                model=self._model,
            )

    async def analyze_sentiment(
        self,
        news: list[dict],
        tweets: str,
        reddit: str,
        fear_greed: int,
        coin: str,
    ) -> SentimentDecision:
        """Analyze combined sentiment data using Claude.

        Returns a SentimentDecision with score, confidence, and factor breakdown.
        """
        t0 = time.monotonic()

        try:
            prompt = build_sentiment_analysis_prompt(
                news, tweets, reddit, fear_greed, coin
            )

            response = await self._client.messages.create(
                model=self._model,
                max_tokens=300,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            latency = (time.monotonic() - t0) * 1000
            self._call_count += 1
            self._total_latency_ms += latency

            text = response.content[0].text
            data = _parse_json_response(text)

            result = SentimentDecision(
                score=max(-1.0, min(1.0, data.get("score", 0.0))),
                confidence=max(0.0, min(1.0, data.get("confidence", 0.5))),
                reason=data.get("reason", "No reason"),
                factors=data.get("factors", []),
                latency_ms=round(latency, 1),
            )

            logger.info(
                "ai_sentiment | score=%.3f | confidence=%.2f | latency=%.0fms",
                result.score,
                result.confidence,
                result.latency_ms,
            )
            return result

        except Exception as e:
            latency = (time.monotonic() - t0) * 1000
            self._call_count += 1
            self._total_latency_ms += latency
            logger.error("sentiment_analysis_error | %s | latency=%.0fms", e, latency)
            return SentimentDecision(
                score=0.0,
                confidence=0.0,
                reason=f"Sentiment analysis failed: {e}",
                latency_ms=round(latency, 1),
            )
