"""Signal scoring — 7-factor weighted score system.

Directly mirrors ``f_calculateSignalStrength`` from svtr.pine v3.8.
Entry and live scoring use the same unified mode (no forEntry asymmetry).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SignalWeights:
    vwap: float = 2.5
    macd: float = 2.5
    rsi: float = 1.0
    volume: float = 2.0
    trend: float = 1.5
    momentum: float = 1.0
    adx: float = 2.0

    @property
    def max_possible(self) -> float:
        return self.vwap + self.macd + self.rsi + self.volume + self.trend + self.momentum + self.adx + 0.5


@dataclass
class SignalResult:
    total_score: float
    vwap: float
    macd: float
    rsi: float
    volume: float
    trend: float
    momentum: float
    adx: float
    adx_mom: float


def calculate_signal_strength(
    row: pd.Series,
    is_long: bool,
    weights: SignalWeights | None = None,
    *,
    adx_threshold: int = 25,
    rsi_threshold: int = 50,
    volume_multiplier: float = 0.5,
) -> SignalResult:
    """Calculate the composite signal score for a single bar.

    Parameters
    ----------
    row : pd.Series
        A single row of an indicator-enriched DataFrame (must contain
        ``close``, ``vwap``, ``atr``, ``macd_line``, ``macd_signal``,
        ``macd_hist``, ``macd_hist_prev``, ``rsi``, ``volume``,
        ``avg_volume``, ``long_term_ma``, ``roc``, ``adx``, ``di_plus``,
        ``di_minus``, ``prev_close``, ``volume_filter``).
    is_long : bool
        ``True`` for long signal, ``False`` for short.
    weights : SignalWeights, optional
        Tunable weights. Uses Pine Script defaults when ``None``.
    """
    if weights is None:
        weights = SignalWeights()

    atr_val = row.get("atr", 1.0) or 1.0
    close = row["close"]
    vwap_val = row["vwap"]
    offset = 0.0

    # ── 1. VWAP Breakout ──────────────────────────────────────────
    vwap_score = 0.0
    if is_long:
        if close > vwap_val + offset:
            breakout_strength = (close - vwap_val) / atr_val
            just_crossed = row.get("prev_close", close) <= vwap_val + offset
            if just_crossed:
                vwap_score = (
                    weights.vwap if breakout_strength > 0.5
                    else weights.vwap * 0.7 if breakout_strength > 0.3
                    else weights.vwap * 0.4
                )
            else:
                vwap_score = (
                    weights.vwap * 0.6 if breakout_strength > 0.5
                    else weights.vwap * 0.5 if breakout_strength > 0.3
                    else weights.vwap * 0.3
                )
    else:
        if close < vwap_val - offset:
            breakout_strength = (vwap_val - close) / atr_val
            just_crossed = row.get("prev_close", close) >= vwap_val - offset
            if just_crossed:
                vwap_score = (
                    weights.vwap if breakout_strength > 0.5
                    else weights.vwap * 0.7 if breakout_strength > 0.3
                    else weights.vwap * 0.4
                )
            else:
                vwap_score = (
                    weights.vwap * 0.6 if breakout_strength > 0.5
                    else weights.vwap * 0.5 if breakout_strength > 0.3
                    else weights.vwap * 0.3
                )

    # ── 2. MACD ───────────────────────────────────────────────────
    macd_score = 0.0
    macd_line = row["macd_line"]
    macd_sig = row["macd_signal"]
    macd_hist = row["macd_hist"]
    macd_hist_prev = row.get("macd_hist_prev", macd_hist)
    macd_hist_prev2 = row.get("macd_hist_prev2", macd_hist_prev)
    macd_strength = abs(macd_line - macd_sig) / atr_val
    macd_accelerating = (
        abs(macd_hist) > abs(macd_hist_prev)
        and abs(macd_hist_prev) > abs(macd_hist_prev2)
    )

    if is_long:
        if macd_line > macd_sig:
            macd_score = weights.macd if macd_hist > macd_hist_prev else weights.macd * 0.6
            if macd_strength > 0.5:
                macd_score *= 1.2
            if macd_accelerating:
                macd_score *= 1.1
    else:
        if macd_line < macd_sig:
            macd_score = weights.macd if macd_hist < macd_hist_prev else weights.macd * 0.6
            if macd_strength > 0.5:
                macd_score *= 1.2
            if macd_accelerating:
                macd_score *= 1.1

    # ── 3. RSI ────────────────────────────────────────────────────
    rsi_score = 0.0
    rsi_val = row["rsi"]
    rsi1 = row.get("rsi_prev1", rsi_val)
    rsi2 = row.get("rsi_prev2", rsi1)

    if is_long:
        if rsi_val > rsi_threshold:
            rsi_score = (
                weights.rsi if rsi_val > 60
                else weights.rsi * 0.7 if rsi_val > rsi_threshold
                else weights.rsi * 0.4
            )
            if 70 < rsi_val < 85:
                rsi_score *= 1.1
            consistency = sum(
                1 for v in [rsi_val, rsi1, rsi2] if v > rsi_threshold
            )
            if consistency == 3:
                rsi_score *= 1.15
    else:
        if rsi_val < rsi_threshold:
            rsi_score = (
                weights.rsi if rsi_val < 40
                else weights.rsi * 0.7 if rsi_val < rsi_threshold
                else weights.rsi * 0.4
            )
            if 15 < rsi_val < 30:
                rsi_score *= 1.1
            consistency = sum(
                1 for v in [rsi_val, rsi1, rsi2] if v < rsi_threshold
            )
            if consistency == 3:
                rsi_score *= 1.15

    # ── 4. Volume ─────────────────────────────────────────────────
    volume_score = 0.0
    avg_vol = row.get("avg_volume", row["volume"])
    vol_ratio = row["volume"] / avg_vol if avg_vol > 0 else 0.0
    if row.get("volume_filter", False):
        volume_score = (
            weights.volume if vol_ratio > 2.0
            else weights.volume * 0.8 if vol_ratio > 1.5
            else weights.volume * 0.6
        )

    # ── 5. Trend ──────────────────────────────────────────────────
    trend_score = 0.0
    long_term_ma = row.get("long_term_ma", close)
    trend_strength = abs(close - long_term_ma) / atr_val if atr_val > 0 else 0.0
    is_uptrend = close > long_term_ma
    is_downtrend = close < long_term_ma

    if is_long and is_uptrend:
        trend_score = (
            weights.trend if trend_strength > 2
            else weights.trend * 0.8 if trend_strength > 1
            else weights.trend * 0.5
        )
    elif not is_long and is_downtrend:
        trend_score = (
            weights.trend if trend_strength > 2
            else weights.trend * 0.8 if trend_strength > 1
            else weights.trend * 0.5
        )
    else:
        trend_score = weights.trend * 0.3

    # ── 6. Momentum (ROC) ────────────────────────────────────────
    momentum_score = 0.0
    roc_val = row.get("roc", 0.0)
    if is_long and roc_val > 0:
        momentum_score = (
            weights.momentum if roc_val > 2
            else weights.momentum * 0.7 if roc_val > 1
            else weights.momentum * 0.4
        )
    elif not is_long and roc_val < 0:
        momentum_score = (
            weights.momentum if roc_val < -2
            else weights.momentum * 0.7 if roc_val < -1
            else weights.momentum * 0.4
        )

    # ── 7. ADX ────────────────────────────────────────────────────
    adx_score = 0.0
    adx_mom_score = 0.0
    adx_val = row.get("adx", 0.0)
    di_plus = row.get("di_plus", 0.0)
    di_minus = row.get("di_minus", 0.0)
    di_plus_prev = row.get("di_plus_prev", di_plus)
    di_minus_prev = row.get("di_minus_prev", di_minus)
    adx_prev = row.get("adx_prev", adx_val)

    if adx_val > adx_threshold:
        if is_long and di_plus > di_minus:
            adx_score = 2.0
            if di_plus > di_plus_prev and adx_val > adx_prev:
                adx_mom_score = 0.5
        elif not is_long and di_minus > di_plus:
            adx_score = 2.0
            if di_minus > di_minus_prev and adx_val > adx_prev:
                adx_mom_score = 0.5
        else:
            adx_score = -0.5

    # ── Total ─────────────────────────────────────────────────────
    total = (
        vwap_score + macd_score + rsi_score + volume_score
        + trend_score + momentum_score + adx_score + adx_mom_score
    )
    total = max(0.0, min(total, 13.5))

    return SignalResult(
        total_score=round(total, 2),
        vwap=round(vwap_score, 2),
        macd=round(macd_score, 2),
        rsi=round(rsi_score, 2),
        volume=round(volume_score, 2),
        trend=round(trend_score, 2),
        momentum=round(momentum_score, 2),
        adx=round(adx_score, 2),
        adx_mom=round(adx_mom_score, 2),
    )
