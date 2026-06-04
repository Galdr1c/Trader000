"""Technical indicators — pandas-ta reimplementation of Pine Script calculations.

Mirrors the indicator calculations from svtr.pine v3.8 with session-aware VWAP.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta


def compute_vwap(
    df: pd.DataFrame,
    smoothing: int = 10,
    anchor: str | None = None,
) -> pd.Series:
    """Session VWAP smoothed with SMA.

    Pine Script: ``ta.sma(ta.vwap(close), sensitivity)``
    When *anchor* is ``None`` the raw session VWAP is used (resets each
    trading session).  ``anchor`` can be ``"D"`` for daily, ``"W"`` for
    weekly, etc.  If you need anchored VWAP that persists across sessions
    (e.g. for 4H+ crypto), pass ``anchor="D"``.
    """
    vwap_raw = ta.vwap(df["high"], df["low"], df["close"], df["volume"], anchor=anchor)
    if smoothing > 1:
        return ta.sma(vwap_raw, length=smoothing)
    return vwap_raw


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, histogram."""
    macd = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    macd_col = f"MACD_{fast}_{slow}_{signal}"
    signal_col = f"MACDs_{fast}_{slow}_{signal}"
    hist_col = f"MACDh_{fast}_{slow}_{signal}"
    return macd[macd_col], macd[signal_col], macd[hist_col]


def compute_rsi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Relative Strength Index."""
    return ta.rsi(df["close"], length=length)


def compute_adx(
    df: pd.DataFrame, length: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """ADX, +DI, -DI."""
    dmi = ta.adx(df["high"], df["low"], df["close"], length=length)
    adx_col = f"ADX_{length}"
    dip_col = f"DMP_{length}"
    dim_col = f"DMN_{length}"
    return dmi[adx_col], dmi[dip_col], dmi[dim_col]


def compute_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range."""
    return ta.atr(df["high"], df["low"], df["close"], length=length)


def compute_roc(df: pd.DataFrame, length: int = 10) -> pd.Series:
    """Rate of Change (%)."""
    return ta.roc(df["close"], length=length)


def compute_ema(df: pd.DataFrame, length: int = 200) -> pd.Series:
    """Exponential Moving Average (main trend filter)."""
    return ta.ema(df["close"], length=length)


def compute_volume_filter(
    df: pd.DataFrame, sma_length: int = 20, multiplier: float = 0.5
) -> pd.Series:
    """Boolean series — True when volume > SMA(volume) * multiplier."""
    avg_vol = ta.sma(df["volume"], length=sma_length)
    return df["volume"] > (avg_vol * multiplier)


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
    vwap_anchor: str | None = None,
) -> pd.DataFrame:
    """Compute all indicators and attach as columns to *df*.

    Returns a new DataFrame with the original OHLCV columns plus all
    indicator columns.  The input is **not** mutated.
    """
    out = df.copy()

    out["vwap"] = compute_vwap(out, smoothing=vwap_smoothing, anchor=vwap_anchor)
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

    return out
