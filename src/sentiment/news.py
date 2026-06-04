"""RSS and CryptoPanic news aggregation for sentiment analysis.

Fetches from:
1. RSS feeds (Cointelegraph, Decrypt, The Block) — free, no key needed
2. CryptoPanic API — free tier (1 req/sec), optional API key for higher limits
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncio
import re

import feedparser
import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def _fetch_cryptopanic(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Fetch recent news from CryptoPanic API.

    Free tier: 1 request/second, no API key required.
    With API key: higher rate limits and more results.
    """
    if not settings.cryptopanic_api_key:
        logger.debug("cryptopanic_no_key | skipping CryptoPanic API")
        return []

    params: dict[str, Any] = {
        "currencies": coin.upper(),
        "filter": "hot",  # hot | important | bullish | bearish | noteworthy | lol
        "kind": "news",  # news | analysis | media
        "regions": "en",  # en | global
    }
    if settings.cryptopanic_api_key:
        params["auth_token"] = settings.cryptopanic_api_key

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    results: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.cryptopanic_api_url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", [])[:20]:
                published_str = item.get("published_at", "")
                try:
                    published = datetime.fromisoformat(
                        published_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    published = datetime.now(timezone.utc)

                if published < cutoff:
                    continue

                # CryptoPanic sentiment labels
                votes = item.get("votes", {})
                sentiment_label = _classify_cryptopanic_sentiment(votes)

                title = item.get("title", "")
                source_url = ""

                news_item: dict[str, Any] = {
                    "title": title,
                    "summary": f"[{sentiment_label}] {item.get('source', {}).get('title', 'CryptoPanic')}",
                    "published": published.isoformat(),
                    "source": "cryptopanic",
                    "url": source_url,
                    "sentiment_label": sentiment_label,
                }
                # Include currencies if present
                currencies = item.get("currencies", [])
                if currencies:
                    news_item["coins"] = [
                        c.get("code", "") for c in currencies if isinstance(c, dict)
                    ]

                results.append(news_item)

    except httpx.TimeoutException:
        logger.warning("cryptopanic_timeout | coin=%s", coin)
    except httpx.HTTPStatusError as e:
        logger.warning("cryptopanic_http_error | %s | %s", e.response.status_code, coin)
    except Exception as e:
        logger.warning("cryptopanic_error | %s | %s", coin, e)

    return results


def _classify_cryptopanic_sentiment(votes: dict) -> str:
    """Classify CryptoPanic votes into a sentiment label.

    votes example: {"liked": 5, "disliked": 1, "important": 2, "lol": 0, "rocket": 3}
    """
    if not isinstance(votes, dict):
        return "neutral"

    liked = votes.get("liked", 0)
    disliked = votes.get("disliked", 0)
    important = votes.get("important", 0)
    rocket = votes.get("rocket", 0)

    positive = liked + rocket + important
    negative = disliked

    if positive > negative * 2:
        return "bullish"
    elif negative > positive * 2:
        return "bearish"
    elif important >= 2:
        return "important"
    return "neutral"


async def _fetch_rss_feeds(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Fetch from configured RSS feeds.

    Returns list of news items matching the coin symbol.
    """
    news: list[dict[str, Any]] = []

    for feed_url in settings.rss_feeds:
        try:
            # feedparser is sync — run in thread to avoid blocking
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "")
                # Match coin symbol in title (case-insensitive)
                if (
                    coin.upper() not in title.upper()
                    and coin.lower() not in title.lower()
                ):
                    continue

                summary = getattr(entry, "summary", "")
                # Strip HTML tags (basic)
                if "<" in summary:
                    summary = re.sub(r"<[^>]+>", "", summary)
                summary = summary[:300]

                published = getattr(entry, "published", "")

                news.append({
                    "title": title,
                    "summary": summary,
                    "published": published,
                    "source": "rss",
                    "url": getattr(entry, "link", ""),
                })
        except Exception as e:
            logger.warning("rss_fetch_error | %s | %s", feed_url, e)

    return news


async def fetch_crypto_news(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Fetch recent crypto news from all sources.

    Combines CryptoPanic API + RSS feeds, deduplicates by title,
    and returns the most recent items capped at 20.

    Returns a list of dicts with keys: title, summary, published, source, url.
    """
    # Fetch from both sources in parallel
    cp_task = _fetch_cryptopanic(coin=coin, hours=hours)
    rss_task = _fetch_rss_feeds(coin=coin, hours=hours)

    cp_news, rss_news = await asyncio.gather(cp_task, rss_task)

    # Combine and deduplicate by title similarity
    all_news: list[dict[str, Any]] = cp_news + rss_news

    # Deduplicate (simple: exact title match)
    seen_titles: set[str] = set()
    unique_news: list[dict[str, Any]] = []
    for item in all_news:
        title_key = item["title"].lower().strip()
        if title_key and title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_news.append(item)

    # Sort by most recent first
    unique_news.sort(key=lambda x: x.get("published", ""), reverse=True)

    logger.info(
        "news_fetched | coin=%s | cp=%d | rss=%d | total=%d",
        coin,
        len(cp_news),
        len(rss_news),
        len(unique_news),
    )

    return unique_news[:20]
