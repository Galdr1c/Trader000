from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.backtesting.parity import evaluate_jesse_candles, evaluate_live_candles
from src.signal_engine.stops import calculate_stop_prices


@pytest.fixture
def candles() -> list[list[float]]:
    path = Path(__file__).parent / "fixtures" / "parity_candles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_jesse_and_live_signal_paths_have_candle_level_parity(candles) -> None:
    live = evaluate_live_candles(candles)
    jesse = evaluate_jesse_candles(candles)

    assert jesse.direction == live.direction
    assert jesse.signal == live.signal
    assert jesse.dynamic_tp == pytest.approx(live.dynamic_tp, abs=1e-9)
    assert jesse.stop_price == pytest.approx(live.stop_price, abs=1e-9)
    assert jesse.max_loss_price == pytest.approx(live.max_loss_price, abs=1e-9)
    assert jesse.indicators.keys() == live.indicators.keys()
    for name, value in live.indicators.items():
        assert jesse.indicators[name] == pytest.approx(value, abs=1e-9), name


def test_parity_honors_strategy_parameter_overrides(candles) -> None:
    parameters = {
        "min_signal_score": 7.0,
        "adx_threshold": 20,
        "atr_multiplier": 3.0,
        "min_tp": 1.5,
        "max_tp": 6.0,
    }

    live = evaluate_live_candles(candles, **parameters)
    jesse = evaluate_jesse_candles(candles, **parameters)

    assert jesse.direction == live.direction
    assert jesse.signal.total_score == live.signal.total_score
    assert jesse.dynamic_tp == live.dynamic_tp
    assert jesse.stop_price == live.stop_price
    assert jesse.max_loss_price == live.max_loss_price


def test_shared_stop_calculation_matches_live_percentage_rules() -> None:
    long_stop, long_max_loss = calculate_stop_prices(
        price=100.0,
        direction="long",
        atr_multiplier=2.5,
        max_loss_pct=4.0,
    )
    short_stop, short_max_loss = calculate_stop_prices(
        price=100.0,
        direction="short",
        atr_multiplier=2.5,
        max_loss_pct=4.0,
    )

    assert (long_stop, long_max_loss) == (95.0, 96.0)
    assert (short_stop, short_max_loss) == (105.0, 104.0)
