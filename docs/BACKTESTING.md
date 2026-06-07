# Jesse Backtesting

Jesse is optional and is not imported by the live bot.

## Installation

```bash
pip install -e ".[backtest]"
```

The integration targets Jesse 2.x and uses its research backtest configuration:
`config`, `routes`, candle dictionaries, warm-up candles, and hyperparameters.

## Candle Input

Commands accept a JSON array in CCXT OHLCV order:

```json
[
  [1700000000000, 100, 110, 90, 105, 1000]
]
```

Fields are timestamp, open, high, low, close, and volume. The adapter converts
them to Jesse's timestamp, open, close, high, low, and volume order.

## Backtest

```bash
python -m src.backtesting.cli backtest data/btc-4h.json \
  --exchange "Binance Perpetual Futures" \
  --symbol BTC-USDT \
  --timeframe 4h
```

The command prints normalized JSON metrics: trades, net profit percentage,
Sharpe ratio, and maximum drawdown.

## Parity

```bash
python -m pytest -q tests/test_backtest_live_parity.py
```

Parity covers indicators, component scores, total score, direction, dynamic
take-profit distance, strategy stop, and hard maximum-loss price. It excludes
fills, slippage, external sentiment, and LLM output.

## Walk-Forward Optimization

Create a bounded JSON grid:

```json
{
  "min_signal_score": [7.5, 8.0, 8.5],
  "adx_threshold": [20, 25, 30],
  "atr_multiplier": [2.0, 2.5, 3.0],
  "min_tp": [1.5, 2.0],
  "max_tp": [5.0, 5.5]
}
```

Run chronological train/test windows:

```bash
python -m src.backtesting.cli walk-forward data/btc-4h.json \
  --grid config/walk-forward-grid.json \
  --train-size 1000 \
  --test-size 250 \
  --min-trades 10 \
  --objective sharpe_ratio \
  --output artifacts/walk-forward.json
```

Only out-of-sample windows are included in the aggregate report.
