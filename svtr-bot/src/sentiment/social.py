"""Social media sentiment collection (placeholder for Agent-Reach integration).

When Agent-Reach is installed, this module uses twitter-cli and rdt-cli
for real-time social media sentiment.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


async def get_twitter_sentiment(coin: str, accounts: list[str] | None = None) -> str:
    """Fetch recent tweets from crypto KOLs via twitter-cli.

    Requires Agent-Reach twitter-cli installed and authenticated.
    Returns concatenated tweet text for Claude analysis.
    """
    if accounts is None:
        accounts = ["whale_alert", "CryptoKaleo", "CoinDesk"]

    results: list[str] = []
    for account in accounts[:5]:
        try:
            result = subprocess.run(
                ["twitter", "timeline", account, "--limit", "3"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                results.append(f"@{account}: {result.stdout[:300]}")
        except FileNotFoundError:
            logger.debug("twitter-cli not installed — skipping")
            break
        except Exception as e:
            logger.warning("twitter_fetch_error | %s | %s", account, e)

    return "\n".join(results) if results else f"[twitter-cli not available for {coin}]"


async def get_reddit_sentiment(coin: str, subreddits: list[str] | None = None) -> str:
    """Fetch hot posts from Reddit via rdt-cli.

    Requires Agent-Reach rdt-cli installed.
    Returns concatenated post titles + scores for Claude analysis.
    """
    if subreddits is None:
        subreddits = ["CryptoCurrency", "bitcoin", "ethtrader"]

    results: list[str] = []
    for sub in subreddits[:3]:
        try:
            result = subprocess.run(
                ["rdt", "search", coin, "--subreddit", sub, "--limit", "5"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                results.append(f"r/{sub}: {result.stdout[:300]}")
        except FileNotFoundError:
            logger.debug("rdt-cli not installed — skipping")
            break
        except Exception as e:
            logger.warning("reddit_fetch_error | %s | %s", sub, e)

    return "\n".join(results) if results else f"[rdt-cli not available for {coin}]"
