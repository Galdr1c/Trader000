"""Tests for Phase 3 — AI Layer enhancements.

Covers: enhanced prompts, composite scorer, decision logger,
Claude client with system prompt.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Composite Scorer
# ═══════════════════════════════════════════════════════════════════════


class TestCompositeScorer:
    def test_strong_buy_signal(self):
        """High score + good conditions → strong_buy."""
        from src.ai_layer.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        result = scorer.score(
            technical_score=12.0,
            technical_max=13.5,
            sentiment_score=0.7,
            sentiment_confidence=0.8,
            ai_approved=True,
            ai_confidence=85,
            ai_risk_level="low",
            funding_rate=0.0005,
            funding_extreme=False,
            volume_ratio=1.8,
            fear_greed=55,
        )
        assert result.decision in ("strong_buy", "buy")
        assert result.score > 0
        assert result.confidence > 0
        assert len(result.components) == 4

    def test_hold_signal(self):
        """Low score → hold."""
        from src.ai_layer.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        result = scorer.score(
            technical_score=4.0,
            technical_max=13.5,
            sentiment_score=0.0,
            sentiment_confidence=0.5,
            ai_approved=None,  # AI disabled
            funding_rate=0.0001,
            funding_extreme=False,
            volume_ratio=1.0,
            fear_greed=50,
        )
        assert result.decision == "hold"

    def test_extreme_funding_penalizes(self):
        """Extreme funding rate should penalize the score."""
        from src.ai_layer.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        good = scorer.score(
            technical_score=10.0, funding_extreme=False, volume_ratio=1.5,
        )
        bad = scorer.score(
            technical_score=10.0, funding_extreme=True, funding_rate=0.003,
            volume_ratio=1.5,
        )
        # Extreme funding should lower the score
        assert bad.score < good.score

    def test_ai_rejection_penalizes(self):
        """AI rejection should lower the score significantly."""
        from src.ai_layer.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        approved = scorer.score(
            technical_score=10.0,
            ai_approved=True,
            ai_confidence=80,
            ai_risk_level="low",
        )
        rejected = scorer.score(
            technical_score=10.0,
            ai_approved=False,
            ai_confidence=80,
            ai_risk_level="high",
        )
        assert rejected.score < approved.score

    def test_low_volume_penalizes(self):
        """Low volume should penalize the score."""
        from src.ai_layer.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        high_vol = scorer.score(technical_score=8.0, volume_ratio=2.0)
        low_vol = scorer.score(technical_score=8.0, volume_ratio=0.3)
        assert low_vol.score < high_vol.score

    def test_to_dict(self):
        """CompositeScore.to_dict returns expected structure."""
        from src.ai_layer.composite_scorer import CompositeScorer

        scorer = CompositeScorer()
        result = scorer.score(technical_score=8.0)
        d = result.to_dict()
        assert "score" in d
        assert "decision" in d
        assert "components" in d
        assert isinstance(d["components"], list)


# ═══════════════════════════════════════════════════════════════════════
# Decision Logger
# ═══════════════════════════════════════════════════════════════════════


class TestDecisionLogger:
    def test_log_signal_eval(self):
        """Decision logger writes JSONL records."""
        from src.ai_layer.decision_logger import AIDecisionLogger

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test_decisions.jsonl"
            logger = AIDecisionLogger(log_path=log_path)

            logger.log_signal_eval(
                symbol="BTC/USDT",
                direction="long",
                signal_score=9.5,
                approved=True,
                ai_confidence=80,
                ai_risk_level="low",
                ai_reason="Strong signal",
                tp_adjustment=0.0,
                funding_rate=0.001,
                fear_greed=55,
                volume_ratio=1.5,
                sentiment_score=0.3,
                latency_ms=500,
                model="claude-sonnet-4-20250514",
            )

            assert log_path.exists()
            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["event_type"] == "signal_eval"
            assert record["symbol"] == "BTC/USDT"
            assert record["approved"] is True

    def test_log_trade_outcome(self):
        """Trade outcome records are logged."""
        from src.ai_layer.decision_logger import AIDecisionLogger

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test_decisions.jsonl"
            logger = AIDecisionLogger(log_path=log_path)

            logger.log_trade_outcome(
                symbol="BTC/USDT",
                direction="long",
                signal_score=9.5,
                pnl_pct=2.5,
                exit_type="dynamic_tp",
                ai_confidence=80,
            )

            lines = log_path.read_text().strip().split("\n")
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["event_type"] == "trade_outcome"
            assert record["outcome_pnl"] == 2.5

    def test_get_stats_empty(self):
        """Stats returns zeros for empty log."""
        from src.ai_layer.decision_logger import AIDecisionLogger

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test_decisions.jsonl"
            logger = AIDecisionLogger(log_path=log_path)
            stats = logger.get_stats()
            assert stats["total_evaluations"] == 0
            assert stats["approval_rate"] == 0.0

    def test_get_stats_with_data(self):
        """Stats calculates correct approval rate and win rate."""
        from src.ai_layer.decision_logger import AIDecisionLogger

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "test_decisions.jsonl"
            logger = AIDecisionLogger(log_path=log_path)

            # Log 3 signal evals: 2 approved, 1 rejected
            for i in range(2):
                logger.log_signal_eval(
                    symbol="BTC", direction="long", signal_score=9.0,
                    approved=True, ai_confidence=80, ai_risk_level="low",
                    ai_reason="ok", tp_adjustment=0, funding_rate=0,
                    fear_greed=50, volume_ratio=1.0, sentiment_score=0,
                    latency_ms=100, model="test",
                )
            logger.log_signal_eval(
                symbol="ETH", direction="short", signal_score=7.0,
                approved=False, ai_confidence=40, ai_risk_level="high",
                ai_reason="weak", tp_adjustment=0, funding_rate=0.002,
                fear_greed=85, volume_ratio=0.8, sentiment_score=-0.5,
                latency_ms=200, model="test",
            )

            # Log 2 outcomes: 1 win, 1 loss
            logger.log_trade_outcome(
                symbol="BTC", direction="long", signal_score=9.0,
                pnl_pct=3.0, exit_type="tp",
            )
            logger.log_trade_outcome(
                symbol="ETH", direction="long", signal_score=8.5,
                pnl_pct=-2.0, exit_type="stop",
            )

            stats = logger.get_stats()
            assert stats["total_evaluations"] == 3
            assert abs(stats["approval_rate"] - 2 / 3) < 0.01
            assert stats["total_outcomes"] == 2
            assert stats["win_rate"] == 0.5


# ═══════════════════════════════════════════════════════════════════════
# Enhanced Prompts
# ═══════════════════════════════════════════════════════════════════════


class TestPrompts:
    def test_system_prompt_exists(self):
        """System prompt is defined."""
        from src.ai_layer.prompts import SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 100
        assert "trading analyst" in SYSTEM_PROMPT.lower()

    def test_build_signal_prompt(self):
        """Signal prompt builder produces formatted output."""
        from src.ai_layer.prompts import build_signal_evaluation_prompt

        prompt = build_signal_evaluation_prompt(
            signal_data={"symbol": "BTC/USDT", "direction": "long", "score": 9.5,
                         "adx": 30, "di_plus": 25, "di_minus": 10, "rsi": 65,
                         "tp_distance": 4.0, "vwap_score": 1.5, "macd_score": 2.0},
            market_context={"funding_rate": 0.001, "funding_is_extreme": False,
                           "open_interest": 50000, "oi_change_pct": 5.0,
                           "volume_ratio": 1.5, "is_high_volume": True, "fear_greed": 55},
            sentiment_data={"news_count": 8, "pos_neg_ratio": 0.7,
                           "sentiment_score": 0.4, "social_mentions": 15},
        )
        assert "BTC/USDT" in prompt
        assert "long" in prompt
        assert "9.5" in prompt
        assert "JSON" in prompt

    def test_build_sentiment_prompt(self):
        """Sentiment prompt builder produces formatted output."""
        from src.ai_layer.prompts import build_sentiment_analysis_prompt

        prompt = build_sentiment_analysis_prompt(
            news=[{"title": "BTC surges", "summary": "Bitcoin rallies to new high"}],
            tweets="@whale: bullish",
            reddit="r/CryptoCurrency: bullish",
            fear_greed=72,
            coin="BTC",
        )
        assert "BTC" in prompt
        assert "BTC surges" in prompt
        assert "JSON" in prompt


# ═══════════════════════════════════════════════════════════════════════
# Claude Client
# ═══════════════════════════════════════════════════════════════════════


class TestClaudeClient:
    def test_stats_initial(self):
        """Initial stats show zero calls."""
        from src.ai_layer.claude_client import ClaudeClient

        with patch("src.ai_layer.claude_client.anthropic.AsyncAnthropic"):
            client = ClaudeClient()
            stats = client.stats
            assert stats["total_calls"] == 0
            assert stats["avg_latency_ms"] == 0.0

    def test_parse_json_response(self):
        """JSON parser handles markdown-wrapped responses."""
        from src.ai_layer.claude_client import _parse_json_response

        # Plain JSON
        assert _parse_json_response('{"approved": true}') == {"approved": True}

        # Markdown wrapped
        wrapped = '```json\n{"approved": false}\n```'
        assert _parse_json_response(wrapped) == {"approved": False}

    @pytest.mark.asyncio
    async def test_evaluate_signal_fail_safe(self):
        """On API error, returns safe rejection."""
        from src.ai_layer.claude_client import ClaudeClient

        with patch("src.ai_layer.claude_client.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(side_effect=Exception("API down"))
            mock_cls.return_value = mock_client

            client = ClaudeClient()
            decision = await client.evaluate_signal(
                {"symbol": "BTC", "direction": "long", "score": 9.0},
                {"funding_rate": 0, "fear_greed": 50},
                {"news_count": 0, "pos_neg_ratio": 0.5, "sentiment_score": 0},
            )
            assert decision.approved is False
            assert decision.risk_level == "high"
            assert "failed" in decision.reason.lower()
