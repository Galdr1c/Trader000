# Phase 5 Design

## Objective

Complete the six Phase 5 roadmap items while preserving the existing live
decision pipeline:

1. Multi-symbol scanner with bounded parallelism
2. Real-time position and P&L dashboard
3. Jesse backtesting integration
4. Backtest-to-live parity tests
5. GitHub Actions CI
6. Walk-forward optimization

Work will be delivered as vertical slices. Each slice must leave the test suite
green and retain single-symbol compatibility.

## Baseline Repair

Phase 1-4 code is present, but the repository does not currently have a clean
verification result. Before Phase 5 behavior is added:

- Pytest collection must exclude executable live-test scripts.
- The TradingAgents integration test must skip with a clear reason when its
  optional dependency is not installed, or the dependency must be declared in
  the relevant optional dependency group.
- The unawaited coroutine warning in the market-data tests must be corrected.
- Ruff must be available through the development dependency set and CI.

These are verification repairs, not changes to trading behavior.

## Architecture

### Configuration

`TRADING_SYMBOLS` becomes the canonical multi-symbol setting. It accepts a
comma-separated list and falls back to the existing `TRADING_SYMBOL` value.
Existing deployments therefore remain valid without configuration changes.

Additional settings will control:

- Maximum concurrent scans
- Maximum simultaneous positions
- Per-symbol exposure
- Total portfolio exposure
- Backtest data and result directories
- Walk-forward train/test window sizes

Configuration parsing will normalize symbols once and reject empty or duplicate
entries.

### Multi-Symbol Scanner

`SignalScanner` will scan symbols concurrently with an `asyncio.Semaphore`.
One failed symbol must produce an error `ScanResult` without cancelling other
symbols. Results will retain deterministic configured-symbol ordering.

Both scheduled scans and `scan_once()` will use the same cycle implementation.
Eligible results will be evaluated independently through the decision engine.
Scanner history will remain bounded and will support filtering by symbol.

### Position and Portfolio State

`PositionManager.active` will be replaced by symbol-keyed active positions.
Compatibility accessors will remain only where existing callers require them.
Opening a second position for an already-active symbol will be rejected.

The manager will expose:

- Active position snapshots
- Position lookup by symbol
- Symbol-specific close operations
- Unrealized P&L using supplied market prices
- Realized trade history in a bounded buffer
- Aggregate realized and unrealized P&L

Portfolio risk checks will enforce maximum simultaneous positions and total
configured exposure before order placement. Existing daily-loss, cooldown, and
consecutive-stop controls remain authoritative.

### Dashboard API and UI

The server will receive scanner and position-manager references at startup.
New read-only endpoints will expose:

- `/api/scanner`: scanner status and recent per-symbol results
- `/api/positions`: active positions, prices, and P&L summary
- `/api/performance`: realized trades and equity/P&L series

The existing dashboard will add symbol cards, an open-position table, aggregate
P&L cards, and a lightweight P&L chart. Partial market-data failures will be
represented as unavailable values rather than causing a dashboard error.

### Jesse Integration

Jesse will be an optional backtesting dependency and will not be imported by
the live application at startup.

The integration will contain:

- A Jesse strategy adapter that delegates indicator and score computation to
  the existing `src.signal_engine` modules
- Candle-data conversion at a single boundary
- Parameter mapping from SVTR settings to a serializable backtest configuration
- A runner interface that can execute a backtest and return normalized metrics
- A CLI entry point for reproducible local and CI smoke backtests

Live exchange, AI, social sentiment, Telegram, and webhook side effects will not
run during backtests. Deterministic fixtures will supply any context required by
the strategy.

### Backtest-Live Parity

Parity tests will feed identical closed-candle fixtures through the live signal
path and the Jesse adapter. They will compare:

- Indicator outputs within numeric tolerances
- Component and total signal scores
- Long, short, or hold decisions
- Dynamic take-profit distance
- Stop-loss calculations

Parity covers deterministic strategy calculations, not fills, slippage,
latency, external sentiment, or LLM output.

### Walk-Forward Optimization

The optimizer will use chronological, non-overlapping out-of-sample windows:

1. Optimize an explicit bounded parameter grid on the training window.
2. Select parameters using a configurable objective with a minimum-trade guard.
3. Evaluate selected parameters on the following test window.
4. Advance both windows and repeat.
5. Aggregate only out-of-sample metrics into the final report.

Initial optimization parameters will be limited to signal threshold, ADX
threshold, ATR multiplier, and dynamic TP bounds. This avoids an unbounded search
space and data-mining-heavy defaults.

Results will include window boundaries, selected parameters, in-sample metrics,
out-of-sample metrics, and an aggregate summary in JSON.

## Data Flow

Live flow:

`configured symbols -> bounded concurrent scan -> signal result -> portfolio
risk check -> decision engine -> exchange/order result -> position state ->
dashboard and metrics`

Backtest flow:

`historical candles -> Jesse adapter -> shared signal calculations -> simulated
orders -> normalized metrics -> parity/optimization reports`

The shared signal modules are the source of truth in both flows.

## Error Handling

- A single scanner request failure is isolated to its symbol.
- Invalid symbol configuration fails at startup with an actionable message.
- Duplicate position attempts are rejected before exchange order placement.
- Missing Jesse dependencies produce a concise installation error only when
  backtest commands are invoked.
- Failed optimization windows are recorded with error details and do not erase
  completed results.
- Dashboard endpoints return valid JSON with degraded status fields when prices
  or external services are unavailable.

## Testing

Development follows red-green-refactor for each behavior.

Required coverage:

- Configuration parsing and backward compatibility
- Scanner concurrency limit, ordering, and failure isolation
- Multiple position lifecycle and aggregate P&L
- Portfolio exposure rejection paths
- Dashboard endpoint schemas and empty/degraded states
- Jesse adapter conversions and normalized runner output
- Candle-level parity fixtures
- Walk-forward window generation, no-leakage boundaries, selection, and report
  aggregation
- CI execution of unit tests, compile checks, and Ruff

Live exchange calls, paid APIs, and network-dependent Jesse downloads are not
required for the default unit suite.

## Delivery Order

1. Repair baseline verification.
2. Add multi-symbol configuration and concurrent scanning.
3. Add symbol-keyed positions and portfolio risk.
4. Add position/P&L APIs and dashboard views.
5. Add the optional Jesse adapter and smoke backtest.
6. Add parity fixtures and tests.
7. Add walk-forward optimization.
8. Add GitHub Actions and update roadmap/documentation.

## Completion Criteria

Phase 5 is complete when:

- All six README checklist items have working implementations.
- Existing single-symbol configuration still starts successfully.
- Unit and parity tests pass without warnings.
- Ruff and Python compilation checks pass.
- The CI workflow runs the same verification commands.
- Jesse and walk-forward commands produce documented machine-readable results.
- README and changelog accurately describe the delivered behavior.
