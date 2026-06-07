"""Sentiment Layer — multi-source market sentiment aggregation."""

from src.sentiment.fear_greed import fetch_fear_greed
from src.sentiment.market_data import fetch_funding_rate, fetch_market_context, fetch_open_interest
from src.sentiment.news import fetch_crypto_news
from src.sentiment.sentiment_pipeline import SentimentCollector, SentimentResult
from src.sentiment.social import get_reddit_sentiment, get_twitter_sentiment

__all__ = [
    "fetch_crypto_news",
    "fetch_fear_greed",
    "fetch_market_context",
    "fetch_funding_rate",
    "fetch_open_interest",
    "SentimentCollector",
    "SentimentResult",
    "get_twitter_sentiment",
    "get_reddit_sentiment",
]
