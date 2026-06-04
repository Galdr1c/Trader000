"""Sentiment Layer — multi-source market sentiment aggregation."""

from src.sentiment.news import fetch_crypto_news
from src.sentiment.fear_greed import fetch_fear_greed

__all__ = ["fetch_crypto_news", "fetch_fear_greed"]
