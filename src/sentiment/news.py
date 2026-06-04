"""RSS and CryptoPanic news aggregation for sentiment analysis.

Fetches from:
1. RSS feeds (Cointelegraph, Decrypt, The Block) — free, no key needed
2. CryptoPanic API — free tier (1 req/sec), optional API key for higher limits

RSS items now include keyword-based sentiment labels (bullish/bearish/neutral).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser
import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# ── Keyword-based sentiment for RSS/news items ─────────────────────

_POSITIVE_KEYWORDS = frozenset([
    "surge", "rally", "bull", "bullish", "moon", "pump", "gain", "profit",
    "breakout", "record", "high", "adoption", "approval", "etf",
    "partnership", "upgrade", "milestone", "accumulation", "institutional",
    "green", "up", "recovery", "boom", "launch", "soar", "jump",
    "positive", "optimistic", "growth", "opportunity", "all-time high",
    "mainnet", "halving", "inflow", "buy", "long",
])

_NEGATIVE_KEYWORDS = frozenset([
    "crash", "dump", "bear", "bearish", "hack", "exploit", "scam",
    "ban", "regulation", "lawsuit", "sec", "fraud", "collapse",
    "decline", "loss", "plunge", "sell-off", "liquidation", "bankrupt",
    "warning", "risk", "down", "red", "fear", "panic", "recession",
    "inflation", "fud", "outflow", "delay", "cancel", "drop", "fall",
    "negative", "pessimistic", "danger", "crisis", "bubble",
])


def _detect_sentiment(text: str) -> str:
    """Detect bullish/bearish/neutral sentiment from text using keywords."""
    if not text:
        return "neutral"
    lower = text.lower()
    pos_count = sum(1 for kw in _POSITIVE_KEYWORDS if kw in lower)
    neg_count = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in lower)
    if pos_count > neg_count and pos_count >= 2:
        return "bullish"
    if neg_count > pos_count and neg_count >= 2:
        return "bearish"
    if pos_count > neg_count:
        return "bullish"
    if neg_count > pos_count:
        return "bearish"
    return "neutral"


def _matches_coin(title: str, coin: str) -> bool:
    """Check if a news title matches a coin symbol or name.

    Handles: BTC, Bitcoin, bitcoin, ETH, Ethereum, ethereum, etc.
    """
    t = title.lower()
    coin_upper = coin.upper()
    coin_lower = coin.lower()

    # Direct match: "BTC", "ETH"
    if coin_upper in t or coin_lower in t:
        return True

    # Common coin name mappings
    coin_names = {
        "BTC": ["bitcoin"],
        "ETH": ["ethereum"],
        "SOL": ["solana"],
        "BNB": ["bnb"],
        "XRP": ["xrp"],
        "ADA": ["cardano"],
        "DOGE": ["dogecoin", "doge"],
        "DOT": ["polkadot"],
        "AVAX": ["avalanche"],
        "MATIC": ["polygon"],
    }
    names = coin_names.get(coin_upper, [coin_lower])
    return any(name in t for name in names)


async def _fetch_cryptopanic(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Fetch recent news from CryptoPanic API."""
    if not settings.cryptopanic_api_key:
        logger.debug("cryptopanic_no_key | skipping CryptoPanic API")
        return []

    params: dict[str, Any] = {
        "currencies": coin.upper(),
        "filter": "hot",
        "kind": "news",
        "regions": "en",
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

                votes = item.get("votes", {})
                sentiment_label = _classify_cryptopanic_sentiment(votes)
                title = item.get("title", "")

                news_item: dict[str, Any] = {
                    "title": title,
                    "summary": item.get("source", {}).get("title", "CryptoPanic"),
                    "published": published.isoformat(),
                    "source": "cryptopanic",
                    "url": "",
                    "sentiment_label": sentiment_label,
                }
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
    """Classify CryptoPanic votes into a sentiment label."""
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
    if negative > positive * 2:
        return "bearish"
    if important >= 2:
        return "important"
    return "neutral"


async def _fetch_rss_feeds(
    coin: str = "BTC",
    hours: int = 4,
) -> list[dict[str, Any]]:
    """Fetch from configured RSS feeds with sentiment detection."""
    news: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for feed_url in settings.rss_feeds:
        try:
            loop = asyncio.get_running_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

            for entry in feed.entries[:30]:
                title = getattr(entry, "title", "")
                if not title:
                    continue

                # Broader coin matching
                if not _matches_coin(title, coin):
                    continue

                summary = getattr(entry, "summary", "")
                if "<" in summary:
                    summary = re.sub(r"<[^>]+>", "", summary)
                summary = summary[:300]

                # Parse published date into ISO format
                published_str = getattr(entry, "published", "") or getattr(entry, "updated", "")
                published = now.isoformat()
                if published_str:
                    try:
                        parsed = feedparser._parse_date(published_str)
                        if parsed:
                            published = datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()
                    except Exception:
                        published = now.isoformat()

                # Add sentiment label via keyword detection
                sentiment_label = _detect_sentiment(title + " " + summary)

                news.append({
                    "title": title,
                    "summary": summary,
                    "published": published,
                    "source": "rss",
                    "url": getattr(entry, "link", ""),
                    "sentiment_label": sentiment_label,
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
    adds sentiment labels, and returns the most recent items capped at 20.
    """
    cp_task = _fetch_cryptopanic(coin=coin, hours=hours)
    rss_task = _fetch_rss_feeds(coin=coin, hours=hours)

    cp_news, rss_news = await asyncio.gather(cp_task, rss_task)

    all_news: list[dict[str, Any]] = cp_news + rss_news

    # Deduplicate by exact title match
    seen_titles: set[str] = set()
    unique_news: list[dict[str, Any]] = []
    for item in all_news:
        title_key = item.get("title", "").lower().strip()
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
