"""Webhook server — receives TradingView alerts and triggers signal evaluation."""

from src.webhook.server import app

__all__ = ["app"]
