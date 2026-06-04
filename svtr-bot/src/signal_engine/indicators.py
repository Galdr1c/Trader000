"""Technical indicators — pure numpy/pandas implementation.

No external TA library dependency. Implements all indicators from svtr.pine v3.8:
- Session VWAP (smoothed with SMA)
- MACD (EMA-based)
- RSI (Wilder's smoothing)
- ADX / +DI / -DI (Wilder's method)
- ATR
- Rate of Change (ROC)
- Exponential Moving Average (EMA)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# Core helpers
# ═══════════════════════════════════════════════════════════════════════

def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=length, min_periods=1).mean()


# ═══════════════════════════════════════════════════════════════════════
# Indicator implementations
# ═══════════════════════════════════════════════════════════════════════

def compute_vwap(
    df: pd.DataFrame,
    smoothing: int = 10,
) -> pd.Series:
    """Session VWAP smoothed with SMA.

    Pine Script: ``ta.sma(ta.vwap(close), sensitivity)``
    Uses cumulative (price*volume) / cumulative(volume) for VWAP,
    then smooths with SMA.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_tpv = (typical_price * df["volume"]).cumsum()
    cum_vol = df["volume"].cumsum()
    vwap_raw = cum_tpv / cum_vol.replace(0, np.nan)
    return sma(vwap_raw, smoothing)


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    macd_line = ema(df["close"], fast) - ema(df["close"], slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """RSI using Wilder's smoothing method."""
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range using Wilder's smoothing."""
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.ewm(alpha=1.0 / length, min_periods=length, adjust=False).mean()
    return atr


def compute_adx(
    df: pd.DataFrame, length: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX, +DI, -DI using Wilder's method."""
    high = df["high"]
    low = df["low"]
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    # When +DM > -DM, keep +DM, else 0 (and vice versa)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    atr = compute_atr(df, length)
    atr_safe = atr.replace(0, np.nan)

    di_plus = 100.0 * ema(plus_dm, length) / atr_safe
    di_minus = 100.0 * ema(minus_dm, length) / atr_safe

    di_sum = di_plus + di_minus
    dx = 100.0 * (di_plus - di_minus).abs() / di_sum.replace(0, np.nan)
    adx = ema(dx.fillna(0.0), length)

    return adx.fillna(0.0), di_plus.fillna(0.0), di_minus.fillna(0.0)


def compute_roc(df: pd.DataFrame, length: int = 10) -> pd.Series:
    """Rate of Change (%)."""
    prev = df["close"].shift(length)
    return ((df["close"] - prev) / prev.replace(0, np.nan) * 100.0).fillna(0.0)


def compute_ema(df: pd.DataFrame, length: int = 200) -> pd.Series:
    """Exponential Moving Average (main trend filter)."""
    return ema(df["close"], length)


def compute_volume_filter(
    df: pd.DataFrame, sma_length: int = 20, multiplier: float = 0.5
) -> pd.Series:
    """Boolean series — True when volume > SMA(volume) * multiplier."""
    avg_vol = sma(df["volume"], sma_length)
    return df["volume"] > (avg_vol * multiplier)


# ═══════════════════════════════════════════════════════════════════════
# Combined computation
# ═══════════════════════════════════════════════════════════════════════

def compute_all(
    df: pd.DataFrame,
    *,
    vwap_smoothing: int = 10,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    rsi_length: int = 14,
    adx_length: int = 14,
    atr_length: int = 14,
    roc_length: int = 10,
    trend_ma_length: int = 200,
    volume_sma_length: int = 20,
    volume_multiplier: float = 0.5,
) -> pd.DataFrame:
    """Compute all indicators and attach as columns to *df*.

    Returns a new DataFrame with the original OHLCV columns plus all
    indicator columns.  The input is **not** mutated.
    """
    out = df.copy()

    out["vwap"] = compute_vwap(out, smoothing=vwap_smoothing)
    out["macd_line"], out["macd_signal"], out["macd_hist"] = compute_macd(
        out, fast=macd_fast, slow=macd_slow, signal=macd_signal
    )
    out["rsi"] = compute_rsi(out, length=rsi_length)
    out["adx"], out["di_plus"], out["di_minus"] = compute_adx(out, length=adx_length)
    out["atr"] = compute_atr(out, length=atr_length)
    out["roc"] = compute_roc(out, length=roc_length)
    out["long_term_ma"] = compute_ema(out, length=trend_ma_length)
    out["volume_filter"] = compute_volume_filter(
        out, sma_length=volume_sma_length, multiplier=volume_multiplier
    )

    # Derived booleans
    out["is_uptrend"] = out["close"] > out["long_term_ma"]
    out["is_downtrend"] = out["close"] < out["long_term_ma"]

    # Previous close for crossover detection
    out["prev_close"] = out["close"].shift(1)

    # Lagged values for scoring (RSI consistency, MACD acceleration, etc.)
    out["rsi_prev1"] = out["rsi"].shift(1)
    out["rsi_prev2"] = out["rsi"].shift(2)
    out["macd_hist_prev"] = out["macd_hist"].shift(1)
    out["macd_hist_prev2"] = out["macd_hist"].shift(2)
    out["di_plus_prev"] = out["di_plus"].shift(1)
    out["di_minus_prev"] = out["di_minus"].shift(1)
    out["adx_prev"] = out["adx"].shift(1)

    # avg_volume for scoring
    out["avg_volume"] = sma(out["volume"], volume_sma_length)

    return out
