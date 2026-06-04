"""Social media sentiment collection via Agent-Reach CLI tools.

Agent-Reach (https://github.com/Panniantong/Agent-Reach) installs and
manages the following CLI tools that we use here:

- twitter-cli: Twitter/X search, timeline, tweet reading (cookie auth)
- rdt-cli: Reddit search, post reading (cookie auth)

These are invoked via subprocess since Agent-Reach is a scaffolding
tool, not a Python library. Authentication requires:
- twitter-cli: logged into x.com in browser (cookie auto-extracted)
- rdt-cli: run `rdt login` once in terminal
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Any

logger = logging.getLogger(__name__)

# ── Health status cache ───────────────────────────────────────────
_tool_status: dict[str, bool] = {}


def _check_tool_available(tool_name: str) -> bool:
    """Check if a CLI tool is available on PATH (cached)."""
    if tool_name not in _tool_status:
        _tool_status[tool_name] = shutil.which(tool_name) is not None
        if not _tool_status[tool_name]:
            logger.debug("tool_not_found | %s — install via agent-reach", tool_name)
    return _tool_status[tool_name]


async def _run_cli(args: list[str], timeout: float = 15.0) -> str | None:
    """Run a CLI command asynchronously and return stdout or None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0 and stdout:
            return stdout.decode("utf-8", errors="replace").strip()
        return None
    except asyncio.TimeoutError:
        logger.warning("cli_timeout | %s", " ".join(args[:2]))
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.warning("cli_error | %s | %s", " ".join(args[:2]), e)
        return None


# ═══════════════════════════════════════════════════════════════════════
# Twitter / X
# ═══════════════════════════════════════════════════════════════════════

async def get_twitter_sentiment(
    coin: str,
    accounts: list[str] | None = None,
) -> str:
    """Fetch recent tweets from crypto KOLs via twitter-cli.

    Requires Agent-Reach twitter-cli installed and authenticated.
    Returns concatenated tweet text for Claude analysis.
    """
    if not _check_tool_available("twitter"):
        return f"[twitter-cli not installed — run: pipx install twitter-cli]"

    if accounts is None:
        accounts = ["whale_alert", "CryptoKaleo", "CoinDesk"]

    results: list[str] = []
    tasks = []

    for account in accounts[:5]:
        tasks.append(
            _run_cli(["twitter", "timeline", account, "--limit", "3"])
        )

    outputs = await asyncio.gather(*tasks)

    for account, output in zip(accounts[:5], outputs):
        if output:
            results.append(f"@{account}: {output[:300]}")

    return "\n".join(results) if results else f"[no tweets found for {coin}]"


# ═══════════════════════════════════════════════════════════════════════
# Reddit
# ═══════════════════════════════════════════════════════════════════════

async def get_reddit_sentiment(
    coin: str,
    subreddits: list[str] | None = None,
) -> str:
    """Fetch hot posts from Reddit via rdt-cli.

    Requires Agent-Reach rdt-cli installed and authenticated.
    Run `rdt login` once to set up cookie auth.
    Returns concatenated post titles + scores for Claude analysis.
    """
    if not _check_tool_available("rdt"):
        return f"[rdt-cli not installed — run: pipx install rdt-cli && rdt login]"

    if subreddits is None:
        subreddits = ["CryptoCurrency", "bitcoin", "ethtrader"]

    results: list[str] = []
    tasks = []

    for sub in subreddits[:3]:
        tasks.append(
            _run_cli(["rdt", "search", coin, "--subreddit", sub, "--limit", "5"])
        )

    outputs = await asyncio.gather(*tasks)

    for sub, output in zip(subreddits[:3], outputs):
        if output:
            results.append(f"r/{sub}: {output[:300]}")

    return "\n".join(results) if results else f"[no Reddit posts found for {coin}]"


# ═══════════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════════

def get_social_health() -> dict[str, Any]:
    """Check which social media CLI tools are available.

    Returns dict with tool availability status.
    Used by monitoring and sentiment pipeline health checks.
    """
    return {
        "twitter_cli": _check_tool_available("twitter"),
        "rdt_cli": _check_tool_available("rdt"),
        "yt_dlp": _check_tool_available("yt-dlp"),
    }
