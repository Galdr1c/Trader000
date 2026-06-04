"""RSS and CryptoPanic news aggregation for sentiment analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# CryptoPanic free API
CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"


async def fetch_crypto_news(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Fetch recent crypto news from RSS feeds and CryptoPanic.

    Returns a list of dicts with keys: title, summary, published, source.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    news: list[dict[str, Any]] = []

    # RSS feeds
    for feed_url in settings.rss_feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = getattr(entry, "title", "")
                if coin.upper() not in title.upper() and coin.lower() not in title.lower():
                    continue
                summary = getattr(entry, "summary", "")[:200]
                published = getattr(entry, "published", "")
                news.append({
                    "title": title,
                    "summary": summary,
                    "published": published,
                    "source": "rss",
                })
        except Exception as e:
            logger.warning("rss_fetch_error | %s | %s", feed_url, e)

    logger.info("news_fetched | coin=%s | count=%d", coin, len(news))
    return news[:20]  # Cap at 20 items


async def fetch_crypto_news_sync(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Synchronous wrapper for use in non-async contexts."""
    return await fetch_crypto_news(coin=coin, hours=hours)
