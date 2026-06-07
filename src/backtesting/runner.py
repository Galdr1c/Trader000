"""Execution boundary for Jesse research backtests."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from src.backtesting.jesse_adapter import BacktestConfig, to_jesse_candles


class JesseUnavailableError(RuntimeError):
    """Raised when an actual Jesse run is requested without the extra."""


class JesseBacktestRunner:
    def __init__(self, executor: Callable[..., Any] | None = None) -> None:
        self._executor = executor

    @staticmethod
    def _load_jesse() -> tuple[Callable[..., Any], Callable[[str, str], str]]:
        try:
            import jesse.helpers as jh
            from jesse.research import backtest
        except ImportError as exc:
            raise JesseUnavailableError(
                "Jesse is optional; install it with: pip install .[backtest]"
            ) from exc
        return backtest, jh.key

    def run(
        self,
        config: BacktestConfig,
        *,
        candles: Sequence[Sequence[float]],
        hyperparameters: dict | None = None,
    ) -> dict[str, float | int]:
        if self._executor is None:
            executor, key_builder = self._load_jesse()
        else:
            executor = self._executor

            def key_builder(exchange: str, symbol: str) -> str:
                return f"{exchange}-{symbol}"

        key = key_builder(config.exchange, config.symbol)
        converted = to_jesse_candles(candles)
        warmup_count = min(config.warm_up_candles, max(0, len(converted) - 1))
        warmup = converted[:warmup_count]
        trading = converted[warmup_count:]
        arguments = dict(
            config=config.jesse_config,
            routes=config.routes,
            data_routes=[],
            candles={
                key: {
                    "exchange": config.exchange,
                    "symbol": config.symbol,
                    "candles": trading,
                }
            },
            hyperparameters=hyperparameters or {},
        )
        if len(warmup):
            arguments["warmup_candles"] = {
                key: {
                    "exchange": config.exchange,
                    "symbol": config.symbol,
                    "candles": warmup,
                }
            }
        raw = executor(**arguments)
        metrics = raw.get("metrics", raw)
        return {
            "trades": int(metrics.get("total", metrics.get("trades", 0))),
            "net_profit_pct": float(
                metrics.get("net_profit_percentage", metrics.get("net_profit_pct", 0.0))
            ),
            "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
            "max_drawdown_pct": float(
                metrics.get("max_drawdown", metrics.get("max_drawdown_pct", 0.0))
            ),
        }
