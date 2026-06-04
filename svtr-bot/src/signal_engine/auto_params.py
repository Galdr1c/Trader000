"""Auto-optimization parameters per exchange & timeframe.

Mirrors the Pine Script auto-optimization system that adapts parameters
based on exchange prefix and timeframe.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AutoParams:
    """Auto-optimized parameter set for a given exchange + timeframe."""

    sensitivity: int = 8
    vwap_exit_confirm_bars: int = 3
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_length: int = 16
    rsi_threshold: int = 52
    volume_mult: float = 0.8
    atr_mult: float = 2.5
    chunk_pct: float = 10.0
    min_tp: float = 2.0
    max_tp: float = 5.5
    pullback_pct: float = 3.5
    trailing_activation_pct: float = 3.0
    max_loss_pct: float = 4.0


# ── Exchange prefixes → market type ──────────────────────────────────

CRYPTO_PREFIXES = {
    "BINANCE", "COINBASE", "BYBIT", "OKX", "BITSTAMP", "GEMINI",
    "KRAKEN", "HTX", "BITMEX", "DERIBIT", "KUCOIN", "MEXC",
    "BITGET", "GATE",
}

FOREX_PREFIXES = {"FX_IDC", "OANDA", "CAPITALCOM", "FX"}

STOCK_PREFIXES = {
    "NASDAQ", "BATS", "SP", "DJ", "XETR", "BIST", "TSE", "LSE",
    "TWSE", "HKEX", "KRX", "SSE", "EURONEXT", "SIX",
}

# ── Timeframe buckets (minutes) ─────────────────────────────────────

TF_SCALPING = 5       # 1m, 3m, 5m
TF_FAST = 15          # 10m, 15m
TF_INTRADAY = 60      # 30m, 45m, 1h
TF_SWING = 240        # 2h, 3h, 4h
TF_POSITION = 1440    # 6h, 8h, 12h, 1d


def _classify_exchange(prefix: str) -> str:
    upper = prefix.upper()
    for p in CRYPTO_PREFIXES:
        if p in upper:
            return "crypto"
    for p in FOREX_PREFIXES:
        if p in upper:
            return "forex"
    for p in STOCK_PREFIXES:
        if p in upper:
            return "stocks"
    return "other"


def _classify_timeframe(minutes: int) -> str:
    if minutes <= TF_SCALPING:
        return "scalping"
    if minutes <= TF_FAST:
        return "fast"
    if minutes <= TF_INTRADAY:
        return "intraday"
    if minutes <= TF_SWING:
        return "swing"
    if minutes <= TF_POSITION:
        return "position"
    return "longterm"


# ── Crypto presets ───────────────────────────────────────────────────

_CRYPTO_PRESETS: dict[str, AutoParams] = {
    "scalping": AutoParams(
        sensitivity=8, vwap_exit_confirm_bars=1, macd_fast=5, macd_slow=13,
        macd_signal=8, rsi_length=9, rsi_threshold=48, volume_mult=2.0,
        atr_mult=1.5, chunk_pct=16.0, min_tp=0.10, max_tp=2.0,
        pullback_pct=0.4, trailing_activation_pct=0.8, max_loss_pct=1.5,
    ),
    "fast": AutoParams(
        sensitivity=6, vwap_exit_confirm_bars=2, macd_fast=7, macd_slow=17,
        macd_signal=8, rsi_length=9, rsi_threshold=45, volume_mult=1.36,
        atr_mult=1.57, chunk_pct=5.5, min_tp=0.8, max_tp=3.0,
        pullback_pct=3.0, trailing_activation_pct=1.5, max_loss_pct=2.3,
    ),
    "intraday": AutoParams(
        sensitivity=12, vwap_exit_confirm_bars=2, macd_fast=8, macd_slow=17,
        macd_signal=9, rsi_length=14, rsi_threshold=50, volume_mult=1.4,
        atr_mult=2.0, chunk_pct=12.0, min_tp=1.5, max_tp=5.0,
        pullback_pct=3.5, trailing_activation_pct=2.0, max_loss_pct=3.0,
    ),
    "swing": AutoParams(
        sensitivity=8, vwap_exit_confirm_bars=3, macd_fast=12, macd_slow=26,
        macd_signal=9, rsi_length=16, rsi_threshold=52, volume_mult=0.8,
        atr_mult=2.5, chunk_pct=10.0, min_tp=2.0, max_tp=5.5,
        pullback_pct=3.5, trailing_activation_pct=3.0, max_loss_pct=4.0,
    ),
    "position": AutoParams(
        sensitivity=10, vwap_exit_confirm_bars=3, macd_fast=12, macd_slow=26,
        macd_signal=9, rsi_length=18, rsi_threshold=50, volume_mult=0.6,
        atr_mult=3.5, chunk_pct=10.0, min_tp=5.0, max_tp=18.0,
        pullback_pct=6.0, trailing_activation_pct=4.0, max_loss_pct=5.0,
    ),
    "longterm": AutoParams(
        sensitivity=12, vwap_exit_confirm_bars=3, macd_fast=14, macd_slow=30,
        macd_signal=9, rsi_length=21, rsi_threshold=55, volume_mult=0.5,
        atr_mult=4.0, chunk_pct=12.5, min_tp=8.0, max_tp=25.0,
        pullback_pct=7.0, trailing_activation_pct=5.0, max_loss_pct=6.0,
    ),
}


def get_auto_params(exchange_prefix: str, timeframe_minutes: int) -> AutoParams:
    """Return optimized parameters for the given exchange + timeframe.

    Parameters
    ----------
    exchange_prefix : str
        Exchange identifier prefix (e.g. ``"BINANCE"``, ``"FX_IDC"``).
    timeframe_minutes : int
        Timeframe in minutes (e.g. ``240`` for 4H, ``60`` for 1H).
    """
    market = _classify_exchange(exchange_prefix)
    tf = _classify_timeframe(timeframe_minutes)

    if market == "crypto":
        return _CRYPTO_PRESETS.get(tf, _CRYPTO_PRESETS["swing"])

    # Forex / stocks / other use the same structure with more conservative defaults
    # (Pine Script uses the same "other" fallback)
    base = _CRYPTO_PRESETS.get(tf, _CRYPTO_PRESETS["swing"])
    if market == "forex":
        # Reduce TP distances for lower-vol forex
        base = AutoParams(
            **{
                **base.__dict__,
                "min_tp": base.min_tp * 0.3,
                "max_tp": base.max_tp * 0.3,
                "pullback_pct": base.pullback_pct * 0.5,
                "trailing_activation_pct": base.trailing_activation_pct * 0.4,
                "max_loss_pct": base.max_loss_pct * 0.5,
            }
        )
    return base
