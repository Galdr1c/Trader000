"""Tests for the Signal Engine — scoring and dynamic TP."""

import numpy as np
import pandas as pd

from src.signal_engine.dynamic_tp import calculate_dynamic_tp
from src.signal_engine.indicators import compute_all
from src.signal_engine.scoring import (
    SignalResult,
    SignalWeights,
    calculate_signal_strength,
)


def _make_row(
    *,
    close: float = 100.0,
    vwap: float = 99.0,
    atr: float = 1.0,
    macd_line: float = 0.5,
    macd_signal: float = 0.3,
    macd_hist: float = 0.2,
    macd_hist_prev: float = 0.1,
    macd_hist_prev2: float = 0.05,
    rsi: float = 55.0,
    rsi_prev1: float = 53.0,
    rsi_prev2: float = 52.0,
    volume: float = 1000.0,
    avg_volume: float = 500.0,
    volume_filter: bool = True,
    long_term_ma: float = 95.0,
    roc: float = 1.5,
    adx: float = 30.0,
    di_plus: float = 25.0,
    di_minus: float = 15.0,
    di_plus_prev: float = 24.0,
    di_minus_prev: float = 16.0,
    adx_prev: float = 29.0,
    prev_close: float = 99.5,
) -> pd.Series:
    """Build a mock indicator row for testing."""
    return pd.Series({
        "close": close,
        "vwap": vwap,
        "atr": atr,
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_hist": macd_hist,
        "macd_hist_prev": macd_hist_prev,
        "macd_hist_prev2": macd_hist_prev2,
        "rsi": rsi,
        "rsi_prev1": rsi_prev1,
        "rsi_prev2": rsi_prev2,
        "volume": volume,
        "avg_volume": avg_volume,
        "volume_filter": volume_filter,
        "long_term_ma": long_term_ma,
        "roc": roc,
        "adx": adx,
        "di_plus": di_plus,
        "di_minus": di_minus,
        "di_plus_prev": di_plus_prev,
        "di_minus_prev": di_minus_prev,
        "adx_prev": adx_prev,
        "prev_close": prev_close,
    })


class TestSignalScoring:
    """Tests for calculate_signal_strength."""

    def test_long_signal_above_vwap(self):
        """Strong long signal: price above VWAP, good MACD, RSI > 50."""
        row = _make_row(close=102, vwap=99, rsi=65, macd_hist=0.5, adx=30, roc=2.5)
        result = calculate_signal_strength(row, is_long=True)

        assert isinstance(result, SignalResult)
        assert result.total_score > 7.0, f"Expected score > 7, got {result.total_score}"
        assert result.vwap > 0, "VWAP score should be positive for price above VWAP"

    def test_short_signal_below_vwap(self):
        """Strong short signal: price below VWAP, bearish MACD."""
        row = _make_row(
            close=97, vwap=100, rsi=35, macd_line=-0.5, macd_signal=-0.3,
            macd_hist=-0.2, macd_hist_prev=-0.1, macd_hist_prev2=-0.05,
            long_term_ma=105, roc=-2.5, adx=30, di_plus=15, di_minus=25,
            di_plus_prev=16, di_minus_prev=24, adx_prev=29, prev_close=100.5,
        )
        result = calculate_signal_strength(row, is_long=False)

        assert result.total_score > 5.0
        assert result.vwap > 0, "VWAP score should be positive for short below VWAP"

    def test_weak_signal_low_score(self):
        """Weak signal: price below VWAP for long, low MACD."""
        row = _make_row(
            close=97, vwap=100, rsi=40, macd_line=-0.5, macd_signal=0,
            macd_hist=-0.5, macd_hist_prev=0.1, macd_hist_prev2=0.2,
            long_term_ma=105, roc=-1.5, adx=15, di_plus=10, di_minus=20,
            prev_close=97.5,
        )
        result = calculate_signal_strength(row, is_long=True)
        assert result.total_score < 6.0

    def test_score_capped_at_13_5(self):
        """Score must never exceed 13.5."""
        row = _make_row(close=200, vwap=90, rsi=75, macd_hist=5.0, adx=50, roc=5.0)
        result = calculate_signal_strength(row, is_long=True)
        assert result.total_score <= 13.5

    def test_score_never_negative(self):
        """Score must never go below 0."""
        row = _make_row(close=80, vwap=100, rsi=20, adx=10)
        result = calculate_signal_strength(row, is_long=True)
        assert result.total_score >= 0.0

    def test_vwap_score_zero_when_far_below(self):
        """Long signal when price is below VWAP → VWAP score = 0."""
        row = _make_row(close=95, vwap=100, prev_close=96)
        result = calculate_signal_strength(row, is_long=True)
        assert result.vwap == 0.0

    def test_custom_weights(self):
        """Custom weights change the score proportionally."""
        row = _make_row(close=102, vwap=99, rsi=65, adx=30, roc=2.5)
        w = SignalWeights(vwap=5.0, macd=5.0)
        result = calculate_signal_strength(row, is_long=True, weights=w)
        assert result.vwap > 0


class TestDynamicTP:
    """Tests for calculate_dynamic_tp."""

    def test_high_score_gives_higher_tp(self):
        """A strong signal should yield a higher TP distance."""
        strong = SignalResult(
            total_score=12.0, vwap=2.0, macd=2.0, rsi=0.8,
            volume=1.5, trend=1.2, momentum=0.8, adx=2.0, adx_mom=0.5,
        )
        weak = SignalResult(
            total_score=7.5, vwap=0.5, macd=0.5, rsi=0.3,
            volume=0.5, trend=0.3, momentum=0.2, adx=0.5, adx_mom=0.0,
        )
        tp_strong = calculate_dynamic_tp(strong, min_tp=2.0, max_tp=5.5)
        tp_weak = calculate_dynamic_tp(weak, min_tp=2.0, max_tp=5.5)
        assert tp_strong > tp_weak

    def test_tp_within_bounds(self):
        """TP must stay within min/max bounds."""
        signal = SignalResult(
            total_score=13.5, vwap=5.0, macd=5.0, rsi=1.0,
            volume=2.0, trend=1.5, momentum=1.0, adx=2.5, adx_mom=0.5,
        )
        tp = calculate_dynamic_tp(signal, min_tp=2.0, max_tp=5.5)
        assert 2.0 <= tp <= 5.5


class TestIndicators:
    """Tests for compute_all indicator pipeline."""

    def _make_ohlcv_df(self, n: int = 100) -> pd.DataFrame:
        """Generate synthetic OHLCV data."""
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        return pd.DataFrame({
            "open": close - np.random.rand(n) * 0.3,
            "high": close + np.random.rand(n) * 0.5,
            "low": close - np.random.rand(n) * 0.5,
            "close": close,
            "volume": np.random.randint(500, 2000, n).astype(float),
        })

    def test_compute_all_adds_columns(self):
        """compute_all should add all indicator columns."""
        df = self._make_ohlcv_df(100)
        result = compute_all(df, vwap_smoothing=5, trend_ma_length=20)

        expected_cols = [
            "vwap", "macd_line", "macd_signal", "macd_hist",
            "rsi", "adx", "di_plus", "di_minus", "atr", "roc",
            "long_term_ma", "volume_filter", "is_uptrend", "is_downtrend",
            "prev_close",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_compute_all_no_nans_in_key_columns(self):
        """Key indicator columns should have no NaN after warmup period."""
        df = self._make_ohlcv_df(200)
        result = compute_all(df, vwap_smoothing=5, trend_ma_length=50)
        # Check last 50 rows (warmup should be complete)
        for col in ["rsi", "adx", "atr", "macd_line"]:
            nan_count = result[col].iloc[-50:].isna().sum()
            assert nan_count == 0, f"NaN in {col} during last 50 rows: {nan_count}"
