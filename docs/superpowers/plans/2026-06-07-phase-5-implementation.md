# Phase 5 Implementation Plan

Design: `docs/superpowers/specs/2026-06-07-phase-5-design.md`

## Task 1: Repair the Verification Baseline

Files:

- Modify `pyproject.toml`
- Modify `tests/test_tradingagents.py`
- Modify `tests/test_phase2_data.py` only if the production contract is correct
- Modify `src/sentiment/market_data.py` only if investigation proves the warning
  originates in production code

Steps:

1. Reproduce pytest collection, optional TradingAgents import, and coroutine
   warning independently.
2. Add or adjust tests/configuration that demonstrate the intended behavior.
3. Exclude executable live scripts from pytest collection.
4. Make the optional TradingAgents test skip explicitly when unavailable.
5. Correct the async mock/await contract at its source.
6. Run the full default test suite with warnings treated as errors.

## Task 2: Add Multi-Symbol Configuration and Scanner Concurrency

Files:

- Modify `src/config/settings.py`
- Modify `src/scanner/scanner.py`
- Modify `src/main.py`
- Add `tests/test_multi_symbol_scanner.py`

Steps:

1. Add failing tests for symbol parsing, fallback, duplicate rejection, bounded
   concurrency, configured ordering, failure isolation, and trade evaluation.
2. Add `TRADING_SYMBOLS` parsing with backward compatibility.
3. Add a shared concurrent scan-cycle implementation using a semaphore.
4. Route scheduled and manual scans through the shared implementation.
5. Add per-symbol history filtering and wire settings into startup.
6. Run scanner tests and the full suite.

## Task 3: Add Multi-Position and Portfolio Risk State

Files:

- Modify `src/decision/position.py`
- Modify `src/decision/risk.py`
- Modify `src/decision/engine.py`
- Modify `src/config/settings.py`
- Modify existing decision tests
- Add `tests/test_portfolio_positions.py`

Steps:

1. Add failing tests for two active symbols, duplicate-symbol rejection,
   symbol-specific close, realized history, and aggregate unrealized P&L.
2. Replace single active position state with a symbol-keyed mapping.
3. Adapt decision-engine position checks to the alert symbol.
4. Add maximum-position and exposure checks before order placement.
5. Preserve existing single-position call compatibility where practical.
6. Run decision tests and the full suite.

## Task 4: Add Position and P&L Dashboard APIs

Files:

- Modify `src/webhook/server.py`
- Modify `src/monitoring/dashboard.py`
- Modify `src/main.py`
- Add `tests/test_dashboard_positions.py`

Steps:

1. Add failing endpoint tests for empty, populated, and degraded price states.
2. Inject scanner and position state into the server.
3. Implement scanner, positions, and performance JSON endpoints.
4. Add dashboard cards, tables, and a dependency-free canvas P&L chart.
5. Ensure HTML output escapes external text before rendering.
6. Run endpoint tests and the full suite.

## Task 5: Add the Optional Jesse Adapter

Files:

- Modify `pyproject.toml`
- Add `src/backtesting/__init__.py`
- Add `src/backtesting/models.py`
- Add `src/backtesting/jesse_adapter.py`
- Add `src/backtesting/runner.py`
- Add `src/backtesting/cli.py`
- Add `tests/test_jesse_adapter.py`

Steps:

1. Add failing tests for candle conversion, parameter mapping, optional
   dependency errors, and normalized result output.
2. Add a `backtest` optional dependency group containing Jesse.
3. Implement dependency-free models and conversions.
4. Import Jesse lazily only from execution boundaries.
5. Implement a runner interface and JSON CLI output.
6. Run adapter tests and the full suite without requiring Jesse installation.

## Task 6: Add Backtest-to-Live Parity Tests

Files:

- Add `tests/fixtures/parity_candles.json`
- Add `src/backtesting/parity.py`
- Add `tests/test_backtest_live_parity.py`

Steps:

1. Create deterministic candle fixtures with warm-up history.
2. Add failing comparisons for indicators, score, direction, TP, and stop.
3. Route both paths through explicit adapters while keeping shared signal
   modules as the source of truth.
4. Define numeric tolerances and produce useful mismatch diagnostics.
5. Run parity tests and the full suite.

## Task 7: Add Walk-Forward Optimization

Files:

- Add `src/backtesting/walk_forward.py`
- Extend `src/backtesting/cli.py`
- Add `tests/test_walk_forward.py`

Steps:

1. Add failing tests for chronological windows, no train/test overlap,
   deterministic parameter selection, minimum-trade filtering, failed-window
   reporting, and aggregate out-of-sample metrics.
2. Implement window generation and bounded grid expansion.
3. Implement runner injection so unit tests do not require Jesse.
4. Write machine-readable reports atomically.
5. Add CLI arguments for windows, grid, objective, and output path.
6. Run optimizer tests and the full suite.

## Task 8: Add CI and Complete Documentation

Files:

- Add `.github/workflows/ci.yml`
- Modify `README.md`
- Modify `CHANGELOG.md`
- Modify `.env.example`
- Modify relevant docs under `docs/`

Steps:

1. Add CI for supported Python versions with dependency caching.
2. Run pytest with warnings as errors, Ruff, and compile checks.
3. Add a dependency-free backtesting CLI smoke test.
4. Document multi-symbol settings, Jesse installation, parity tests, and
   walk-forward commands.
5. Mark Phase 5 complete only after all verification commands pass.

## Final Verification

Run:

```powershell
python -m pytest -q -W error
python -m ruff check .
python -m compileall -q src tests
git diff --check
```

Review the Phase 5 design completion criteria line by line before updating the
roadmap status.
