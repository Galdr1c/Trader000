"""Backtest-to-live signal parity helpers."""

from __future__ import annotations

from collections.abc import Sequence

from src.backtesting.jesse_adapter import (
    SignalEvaluation,
    SVTRSignalAdapter,
    to_jesse_candles,
)


def evaluate_live_candles(
    candles: Sequence[Sequence[float]],
    **parameters,
) -> SignalEvaluation:
    """Evaluate candles in the live CCXT OHLCV representation."""
    return SVTRSignalAdapter().evaluate(candles, **parameters)


def evaluate_jesse_candles(
    candles: Sequence[Sequence[float]],
    **parameters,
) -> SignalEvaluation:
    """Evaluate after crossing the Jesse candle-format boundary."""
    jesse_candles = to_jesse_candles(candles)
    ccxt_candles = [
        [timestamp, open_, high, low, close, volume]
        for timestamp, open_, close, high, low, volume in jesse_candles
    ]
    return SVTRSignalAdapter().evaluate(ccxt_candles, **parameters)
