"""Tests for Phase 2 — Data Integration modules.

Covers: news aggregation, market data, sentiment pipeline, market context.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Fear & Greed
# ═══════════════════════════════════════════════════════════════════════


class TestFearGreed:
    @pytest.mark.asyncio
    async def test_fetch_fear_greed_success(self):
        """Successful fetch returns integer 0-100."""
        from src.sentiment.fear_greed import fetch_fear_greed

        mock_data = {"data": [{"value": "72"}]}
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("src.sentiment.fear_greed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_fear_greed()
            assert result == 72
            assert 0 <= result <= 100

    @pytest.mark.asyncio
    async def test_fetch_fear_greed_failure_returns_neutral(self):
        """On failure, returns 50 (neutral)."""
        from src.sentiment.fear_greed import fetch_fear_greed

        with patch("src.sentiment.fear_greed.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("timeout"))
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await fetch_fear_greed()
            assert result == 50


# ═══════════════════════════════════════════════════════════════════════
# News (RSS + CryptoPanic)
# ═══════════════════════════════════════════════════════════════════════


class TestNews:
    @pytest.mark.asyncio
    async def test_fetch_crypto_news_no_cryptopanic_key(self):
        """Without CryptoPanic key, only RSS feeds are used."""
        from src.sentiment.news import fetch_crypto_news

        with patch("src.sentiment.news.settings") as mock_settings:
            mock_settings.cryptopanic_api_key = ""
            mock_settings.rss_feeds = []
            mock_settings.cryptopanic_api_url = "https://cryptopanic.com/api/v1/posts/"

            result = await fetch_crypto_news(coin="BTC", hours=4)
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_cryptopanic_skipped_without_key(self):
        """CryptoPanic returns empty list when no API key is set."""
        from src.sentiment.news import _fetch_cryptopanic

        with patch("src.sentiment.news.settings") as mock_settings:
            mock_settings.cryptopanic_api_key = ""

            result = await _fetch_cryptopanic(coin="BTC")
            assert result == []


# ═══════════════════════════════════════════════════════════════════════
# Market Data
# ═══════════════════════════════════════════════════════════════════════


class TestMarketData:
    @pytest.mark.asyncio
    async def test_fetch_funding_rate_success(self):
        """Funding rate fetch returns structured dict."""
        from src.sentiment.market_data import fetch_funding_rate

        mock_exchange = AsyncMock()
        mock_exchange.get_funding_rate = AsyncMock(return_value=0.0005)

        result = await fetch_funding_rate(mock_exchange, "BTC/USDT:USDT")
        assert result["current_rate"] == 0.0005
        assert result["current_rate_pct"] == 0.05
        assert result["is_extreme"] is False
        assert result["direction"] == "neutral"

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_extreme(self):
        """Extreme funding rate is flagged."""
        from src.sentiment.market_data import fetch_funding_rate

        mock_exchange = AsyncMock()
        mock_exchange.get_funding_rate = AsyncMock(return_value=0.015)

        result = await fetch_funding_rate(mock_exchange, "BTC/USDT:USDT")
        assert result["is_extreme"] is True
        assert result["direction"] == "long_heavy"

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_negative(self):
        """Negative funding rate indicates short pressure."""
        from src.sentiment.market_data import fetch_funding_rate

        mock_exchange = AsyncMock()
        mock_exchange.get_funding_rate = AsyncMock(return_value=-0.005)

        result = await fetch_funding_rate(mock_exchange, "BTC/USDT:USDT")
        assert result["direction"] == "short_heavy"

    @pytest.mark.asyncio
    async def test_fetch_funding_rate_error(self):
        """On error, returns safe defaults."""
        from src.sentiment.market_data import fetch_funding_rate

        mock_exchange = AsyncMock()
        mock_exchange.get_funding_rate = AsyncMock(side_effect=Exception("api error"))

        result = await fetch_funding_rate(mock_exchange, "BTC/USDT:USDT")
        assert result["current_rate"] == 0.0
        assert result["direction"] == "unknown"

    @pytest.mark.asyncio
    async def test_fetch_volume_analysis(self):
        """Volume analysis returns ratio and high volume flag."""
        from src.sentiment.market_data import fetch_volume_analysis

        mock_exchange = AsyncMock()
        mock_exchange.get_ohlcv = AsyncMock(
            return_value=[
                [0, 100, 110, 90, 105, 1000] for _ in range(24)
            ]
            + [[0, 100, 110, 90, 105, 3000]]  # Last candle: 3x volume
        )

        result = await fetch_volume_analysis(mock_exchange, "BTC/USDT:USDT")
        assert result["volume_ratio"] > 1.0
        assert result["is_high_volume"] is True

    @pytest.mark.asyncio
    async def test_fetch_market_context(self):
        """Market context aggregates all data sources."""
        from src.sentiment.market_data import fetch_market_context

        mock_exchange = AsyncMock()
        mock_exchange.get_funding_rate = AsyncMock(return_value=0.001)
        mock_exchange.exchange = MagicMock()
        mock_exchange.exchange.fetch_open_interest = AsyncMock(
            return_value={"openInterestAmount": 50000, "baseVolume": "BTC", "quoteVolume": "USDT"}
        )
        mock_exchange.get_ohlcv = AsyncMock(
            return_value=[[0, 100, 110, 90, 105, 1000] for _ in range(25)]
        )

        result = await fetch_market_context(mock_exchange, "BTC/USDT:USDT")
        assert "funding_rate" in result
        assert "open_interest" in result
        assert "volume_ratio" in result


# ═══════════════════════════════════════════════════════════════════════
# Social Media
# ═══════════════════════════════════════════════════════════════════════


class TestSocial:
    @pytest.mark.asyncio
    async def test_twitter_sentiment_no_cli(self):
        """When twitter-cli is not installed, returns placeholder."""
        from src.sentiment.social import get_twitter_sentiment

        with patch("src.sentiment.social.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("twitter not found")

            result = await get_twitter_sentiment("BTC")
            assert "[not available" in result.lower() or "twitter-cli" in result.lower()

    @pytest.mark.asyncio
    async def test_reddit_sentiment_no_cli(self):
        """When rdt-cli is not installed, returns placeholder."""
        from src.sentiment.social import get_reddit_sentiment

        with patch("src.sentiment.social.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("rdt not found")

            result = await get_reddit_sentiment("BTC")
            assert "[not available" in result.lower() or "rdt-cli" in result.lower()


# ═══════════════════════════════════════════════════════════════════════
# Sentiment Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestSentimentPipeline:
    @pytest.mark.asyncio
    async def test_collect_without_ai(self):
        """SentimentCollector works without AI client."""
        from src.sentiment.sentiment_pipeline import SentimentCollector

        collector = SentimentCollector(ai_client=None)

        with patch("src.sentiment.sentiment_pipeline.fetch_crypto_news") as mock_news, \
             patch("src.sentiment.sentiment_pipeline.fetch_fear_greed") as mock_fg, \
             patch("src.sentiment.sentiment_pipeline.get_twitter_sentiment") as mock_tw, \
             patch("src.sentiment.sentiment_pipeline.get_reddit_sentiment") as mock_rd:

            mock_news.return_value = [
                {"title": "BTC surges to new high", "summary": "Bitcoin rallies", "source": "rss"},
                {"title": "BTC crash imminent", "summary": "Bear market warning", "source": "rss"},
            ]
            mock_fg.return_value = 72
            mock_tw.return_value = "[twitter-cli not available for BTC]"
            mock_rd.return_value = "[rdt-cli not available for BTC]"

            result = await collector.collect("BTC")
            assert -1.0 <= result.score <= 1.0
            assert result.news_count == 2
            assert result.confidence == 0.5  # No AI = lower confidence

    @pytest.mark.asyncio
    async def test_rule_based_score_bullish(self):
        """Rule-based score is positive for bullish signals."""
        from src.sentiment.sentiment_pipeline import SentimentCollector

        score = SentimentCollector._compute_rule_based_score(
            fear_greed=75, pos_neg_ratio=0.8, news_count=10, has_social=True
        )
        assert score > 0

    @pytest.mark.asyncio
    async def test_rule_based_score_bearish(self):
        """Rule-based score is negative for bearish signals."""
        from src.sentiment.sentiment_pipeline import SentimentCollector

        score = SentimentCollector._compute_rule_based_score(
            fear_greed=20, pos_neg_ratio=0.2, news_count=10, has_social=True
        )
        assert score < 0

    def test_sentiment_result_to_dict(self):
        """SentimentResult.to_dict returns expected keys."""
        from src.sentiment.sentiment_pipeline import SentimentResult

        result = SentimentResult(score=0.5, confidence=0.8, reason="test", news_count=5)
        d = result.to_dict()
        assert "score" in d
        assert "confidence" in d
        assert "reason" in d
        assert d["news_count"] == 5


# ═══════════════════════════════════════════════════════════════════════
# Keyword Sentiment Helpers
# ═══════════════════════════════════════════════════════════════════════


class TestKeywordSentiment:
    def test_positive_keywords_detected(self):
        from src.sentiment.sentiment_pipeline import _is_positive_news
        assert _is_positive_news("Bitcoin surges to new all-time high")
        assert _is_positive_news("ETH rally continues with record gains")
        assert not _is_positive_news("Market remains unchanged")

    def test_negative_keywords_detected(self):
        from src.sentiment.sentiment_pipeline import _is_negative_news
        assert _is_negative_news("Crypto crash wipes out billions")
        assert _is_negative_news("Bitcoin bear market deepens with massive sell-off")
        assert not _is_negative_news("Market remains unchanged")
