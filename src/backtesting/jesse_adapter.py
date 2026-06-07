"""Jesse data conversion and shared SVTR signal adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from src.signal_engine.dynamic_tp import calculate_dynamic_tp
from src.signal_engine.indicators import compute_all
from src.signal_engine.scoring import SignalResult, calculate_signal_strength
from src.signal_engine.stops import calculate_stop_prices


@dataclass(frozen=True)
class BacktestConfig:
    exchange: str = "Binance Perpetual Futures"
    symbol: str = "BTC-USDT"
    timeframe: str = "4h"
    strategy: str = "SVTR"
    starting_balance: float = 10_000
    fee: float = 0.0005
    leverage: int = 1
    warm_up_candles: int = 210

    @property
    def jesse_config(self) -> dict:
        return {
            "starting_balance": self.starting_balance,
            "fee": self.fee,
            "type": "futures",
            "futures_leverage": self.leverage,
            "futures_leverage_mode": "cross",
            "exchange": self.exchange,
            "warm_up_candles": self.warm_up_candles,
        }

    @property
    def routes(self) -> list[dict]:
        return [{
            "exchange": self.exchange,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }]


def to_jesse_candles(candles: Sequence[Sequence[float]]) -> np.ndarray:
    """Convert CCXT OHLCV order to Jesse's timestamp/open/close/high/low/volume."""
    return np.asarray(
        [
            [timestamp, open_, close, high, low, volume]
            for timestamp, open_, high, low, close, volume in candles
        ],
        dtype=float,
    )


def candles_to_dataframe(candles: Sequence[Sequence[float]]) -> pd.DataFrame:
    """Convert CCXT OHLCV candles to the signal engine DataFrame contract."""
    return pd.DataFrame(
        candles,
        columns=["timestamp", "open", "high", "low", "close", "volume"],
        dtype=float,
    )


@dataclass(frozen=True)
class SignalEvaluation:
    direction: str
    signal: SignalResult
    dynamic_tp: float
    stop_price: float
    max_loss_price: float
    indicators: dict[str, float]


class SVTRSignalAdapter:
    """Evaluate candle data through the production signal modules."""

    def evaluate(
        self,
        candles: Sequence[Sequence[float]],
        *,
        min_signal_score: float = 8.0,
        adx_threshold: int = 25,
        atr_multiplier: float = 2.5,
        max_loss_pct: float = 4.0,
        min_tp: float = 2.0,
        max_tp: float = 5.5,
    ) -> SignalEvaluation:
        frame = compute_all(candles_to_dataframe(candles), adx_length=14)
        row = frame.iloc[-1]
        long_signal = calculate_signal_strength(
            row,
            is_long=True,
            adx_threshold=adx_threshold,
        )
        short_signal = calculate_signal_strength(
            row,
            is_long=False,
            adx_threshold=adx_threshold,
        )
        if long_signal.total_score >= short_signal.total_score:
            signal = long_signal
            direction = "long" if signal.total_score >= min_signal_score else "hold"
        else:
            signal = short_signal
            direction = "short" if signal.total_score >= min_signal_score else "hold"

        dynamic_tp = calculate_dynamic_tp(signal, min_tp=min_tp, max_tp=max_tp)
        close = float(row["close"])
        stop_direction = direction if direction in {"long", "short"} else "long"
        stop_price, max_loss_price = calculate_stop_prices(
            price=close,
            direction=stop_direction,
            atr_multiplier=atr_multiplier,
            max_loss_pct=max_loss_pct,
        )
        indicator_names = ("vwap", "macd_line", "macd_signal", "rsi", "adx", "atr")
        indicators = {name: float(row[name]) for name in indicator_names}
        return SignalEvaluation(
            direction,
            signal,
            dynamic_tp,
            stop_price,
            max_loss_price,
            indicators,
        )
