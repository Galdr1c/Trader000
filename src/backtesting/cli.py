"""Command-line entry points for backtesting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.backtesting.jesse_adapter import BacktestConfig
from src.backtesting.runner import JesseBacktestRunner
from src.backtesting.walk_forward import WalkForwardOptimizer


def main() -> None:
    parser = argparse.ArgumentParser(description="SVTR Jesse backtesting tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser("backtest")
    _add_common_arguments(backtest_parser)

    walk_parser = subparsers.add_parser("walk-forward")
    _add_common_arguments(walk_parser)
    walk_parser.add_argument("--grid", type=Path, required=True, help="JSON parameter grid")
    walk_parser.add_argument("--train-size", type=int, required=True)
    walk_parser.add_argument("--test-size", type=int, required=True)
    walk_parser.add_argument("--min-trades", type=int, default=1)
    walk_parser.add_argument("--objective", default="sharpe_ratio")
    walk_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candle_data = json.loads(args.candles.read_text(encoding="utf-8"))
    config = BacktestConfig(
        exchange=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe,
    )
    runner = JesseBacktestRunner()
    if args.command == "backtest":
        result = runner.run(config, candles=candle_data)
    else:
        grid = json.loads(args.grid.read_text(encoding="utf-8"))
        optimizer = WalkForwardOptimizer(
            lambda candles, parameters: runner.run(
                config,
                candles=candles,
                hyperparameters=parameters,
            )
        )
        result = optimizer.run(
            candles=candle_data,
            parameter_grid=grid,
            train_size=args.train_size,
            test_size=args.test_size,
            min_trades=args.min_trades,
            objective=args.objective,
            output_path=args.output,
        )
    print(json.dumps(result, sort_keys=True))


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("candles", type=Path, help="JSON file containing CCXT OHLCV candles")
    parser.add_argument("--symbol", default="BTC-USDT")
    parser.add_argument("--exchange", default="Binance Perpetual Futures")
    parser.add_argument("--timeframe", default="4h")


if __name__ == "__main__":
    main()
