"""Centralized configuration via pydantic-settings.

All tunables live here — nothing hardcoded in business logic.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
    )

    # ── Exchange ──────────────────────────────────────────────────
    exchange_id: str = "binance"
    exchange_api_key: str = ""
    exchange_secret: str = ""
    exchange_testnet: bool = True

    # ── Anthropic / Claude ────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # ── Telegram ──────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── Webhook ───────────────────────────────────────────────────
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_secret: str = ""

    # ── Strategy ──────────────────────────────────────────────────
    min_signal_score: float = 8.0
    position_size_pct: float = 20.0
    daily_max_loss_pct: float = 5.0
    consecutive_stop_limit: int = 3
    cooldown_hours: int = 24
    trading_symbol: str = "BTC/USDT:USDT"
    timeframe: Timeframe = Timeframe.H4
    use_dynamic_tp: bool = True
    take_profit_pct: float = 5.0
    chunk_pct: float = 10.0
    pullback_pct: float = 4.0
    tp_levels: int = 15
    min_tp_distance: float = 2.0
    max_tp_distance: float = 5.5
    use_auto_adjust: bool = True
    use_adx_trend: bool = True
    adx_threshold: int = 25
    adx_length: int = 14
    atr_period: int = 14
    atr_multiplier: float = 2.5
    use_stop_loss: bool = True
    use_trailing_stop: bool = False
    trailing_activation_pct: float = 3.0
    use_max_loss: bool = True
    max_loss_pct: float = 4.0
    trend_ma_period: int = 200

    # ── AI Layer ──────────────────────────────────────────────────
    ai_enabled: bool = True
    ai_confidence_threshold: int = 60
    ai_max_tokens: int = 500

    # ── Sentiment ─────────────────────────────────────────────────
    sentiment_enabled: bool = True
    cryptopanic_api_key: str = ""
    cryptopanic_api_url: str = "https://cryptopanic.com/api/v1/posts/"
    rss_feeds: list[str] = Field(
        default=[
            "https://cointelegraph.com/rss",
            "https://decrypt.co/feed",
            "https://www.theblock.co/rss.xml",
        ]
    )
    fear_greed_api_url: str = "https://api.alternative.me/fng/"

    # ── Market Data ───────────────────────────────────────────────
    funding_rate_alert_threshold: float = 0.01  # 1% = extreme
    oi_change_alert_threshold: float = 10.0  # 10% change = notable

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Paths ─────────────────────────────────────────────────────
    data_dir: Path = Path("data")
    log_dir: Path = Path("logs")


settings = Settings()
