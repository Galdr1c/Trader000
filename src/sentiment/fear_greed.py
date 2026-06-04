"""Fear & Greed Index API client."""

from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


async def fetch_fear_greed() -> int:
    """Fetch the current Crypto Fear & Greed Index.

    Returns an integer 0-100 (0=Extreme Fear, 100=Extreme Greed).
    Defaults to 50 (Neutral) on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.fear_greed_api_url)
            resp.raise_for_status()
            data = resp.json()
            value = int(data["data"][0]["value"])
            return max(0, min(100, value))
    except Exception as e:
        logger.warning("fear_greed_fetch_error | %s", e)
        return 50  # Neutral default
