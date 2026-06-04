"""Dynamic Take Profit calculation.

Reimplements ``f_calculateDynamicTP`` from svtr.pine v3.8.
"""

from __future__ import annotations

from src.signal_engine.scoring import SignalResult, SignalWeights


def calculate_dynamic_tp(
    signal: SignalResult,
    *,
    min_tp: float = 2.0,
    max_tp: float = 5.5,
    weights: SignalWeights | None = None,
) -> float:
    """Return the dynamic TP distance (%) based on signal quality.

    Parameters
    ----------
    signal : SignalResult
        The signal scoring result for the entry bar.
    min_tp : float
        Minimum TP distance (%) — used for weak signals.
    max_tp : float
        Maximum TP distance (%) — used for very strong signals.
    weights : SignalWeights, optional
        TP calculation weights (Pine defaults used if None).
    """
    if weights is None:
        weights = SignalWeights()

    # Base TP from score ratio (7.0 = baseline, 13.5 = max)
    score_ratio = max(0.0, min(1.0, (signal.total_score - 7.0) / 6.0))
    base_tp = min_tp + score_ratio * (max_tp - min_tp)

    # Multiplier from individual components
    trend_mult = 1.0
    if signal.trend > weights.trend * 0.8:
        trend_mult = 1.2
    elif signal.trend < weights.trend * 0.5:
        trend_mult = 0.85

    momentum_mult = 1.0
    if signal.momentum > weights.momentum * 0.8:
        momentum_mult = 1.15
    elif signal.momentum < weights.momentum * 0.5:
        momentum_mult = 0.9

    volume_mult = 1.0
    if signal.volume > weights.volume * 0.8:
        volume_mult = 1.1

    macd_mult = 1.0
    if signal.macd > weights.macd * 0.8:
        macd_mult = 1.1

    adx_mult = 1.0
    if signal.adx > weights.adx * 0.8:
        adx_mult = 1.375  # 1.0 + 1.5*0.25
        if signal.adx_mom > 0:
            adx_mult += 0.15
    elif signal.adx < weights.adx * 0.5:
        adx_mult = 0.7  # 1.0 - 1.5*0.2

    total_mult = (trend_mult + momentum_mult + volume_mult + macd_mult + adx_mult) / 5.0
    final_tp = base_tp * total_mult
    return round(max(min_tp, min(max_tp, final_tp)), 2)
