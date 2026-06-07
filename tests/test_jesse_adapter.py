from __future__ import annotations

import builtins

import pytest

from src.backtesting.jesse_adapter import (
    BacktestConfig,
    candles_to_dataframe,
    to_jesse_candles,
)
from src.backtesting.runner import JesseBacktestRunner, JesseUnavailableError

CANDLES = [
    [1_700_000_000_000, 100.0, 110.0, 90.0, 105.0, 1_000.0],
    [1_700_003_600_000, 105.0, 115.0, 100.0, 112.0, 1_200.0],
]


def test_ccxt_candles_convert_to_jesse_order() -> None:
    converted = to_jesse_candles(CANDLES)

    assert converted.tolist()[0] == [
        1_700_000_000_000,
        100.0,
        105.0,
        110.0,
        90.0,
        1_000.0,
    ]


def test_candles_convert_to_signal_dataframe() -> None:
    frame = candles_to_dataframe(CANDLES)

    assert list(frame.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    assert frame.iloc[-1]["close"] == 112.0


def test_backtest_config_builds_jesse_payload() -> None:
    config = BacktestConfig(
        exchange="Binance Perpetual Futures",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="SVTR",
        starting_balance=20_000,
        fee=0.0004,
        leverage=2,
        warm_up_candles=210,
    )

    assert config.jesse_config["starting_balance"] == 20_000
    assert config.jesse_config["futures_leverage"] == 2
    assert config.routes[0]["strategy"] == "SVTR"


def test_runner_normalizes_executor_result() -> None:
    def executor(**kwargs):
        assert kwargs["config"]["starting_balance"] == 10_000
        return {
            "metrics": {
                "total": 7,
                "net_profit_percentage": 12.5,
                "sharpe_ratio": 1.2,
                "max_drawdown": 8.0,
            }
        }

    result = JesseBacktestRunner(executor=executor).run(
        BacktestConfig(),
        candles=CANDLES,
    )

    assert result["trades"] == 7
    assert result["net_profit_pct"] == 12.5
    assert result["sharpe_ratio"] == 1.2
    assert result["max_drawdown_pct"] == 8.0


def test_runner_reports_missing_optional_jesse_dependency(monkeypatch) -> None:
    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name.startswith("jesse"):
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(JesseUnavailableError, match=r"pip install .\[backtest\]"):
        JesseBacktestRunner().run(BacktestConfig(), candles=CANDLES)
