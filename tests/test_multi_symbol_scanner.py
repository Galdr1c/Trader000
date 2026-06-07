from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.config.settings import Settings
from src.scanner.scanner import ScanResult, SignalScanner


def test_trading_symbols_fall_back_to_legacy_symbol() -> None:
    config = Settings(
        _env_file=None,
        trading_symbol="BTC/USDT:USDT",
        trading_symbols="",
    )

    assert config.parsed_trading_symbols == ["BTC/USDT:USDT"]


def test_trading_symbols_parse_and_normalize_comma_separated_values() -> None:
    config = Settings(
        _env_file=None,
        trading_symbols=" btc/usdt:usdt, ETH/USDT:USDT ",
    )

    assert config.parsed_trading_symbols == ["BTC/USDT:USDT", "ETH/USDT:USDT"]


def test_trading_symbols_reject_duplicates() -> None:
    config = Settings(
        _env_file=None,
        trading_symbols="BTC/USDT:USDT,btc/usdt:usdt",
    )

    with pytest.raises(ValueError, match="duplicate"):
        _ = config.parsed_trading_symbols


@pytest.mark.asyncio
async def test_scan_once_preserves_order_and_bounds_concurrency(monkeypatch) -> None:
    scanner = SignalScanner(
        mcp_client=AsyncMock(),
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        max_concurrency=2,
    )
    active = 0
    peak = 0

    async def fake_scan(symbol: str) -> ScanResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return ScanResult(symbol=symbol)

    monkeypatch.setattr(scanner, "_scan_symbol", fake_scan)

    results = await scanner.scan_once()

    assert [result.symbol for result in results] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert peak == 2


@pytest.mark.asyncio
async def test_scan_once_isolates_symbol_failures(monkeypatch) -> None:
    scanner = SignalScanner(
        mcp_client=AsyncMock(),
        symbols=["BTCUSDT", "ETHUSDT"],
        max_concurrency=2,
    )

    async def fake_scan(symbol: str) -> ScanResult:
        if symbol == "BTCUSDT":
            raise RuntimeError("provider unavailable")
        return ScanResult(symbol=symbol, signal_score=9.0, direction="long")

    monkeypatch.setattr(scanner, "_scan_symbol", fake_scan)

    results = await scanner.scan_once()

    assert results[0].symbol == "BTCUSDT"
    assert results[0].reason == "scan_error: provider unavailable"
    assert results[1].signal_score == 9.0


@pytest.mark.asyncio
async def test_scan_once_evaluates_each_eligible_symbol(monkeypatch) -> None:
    scanner = SignalScanner(
        mcp_client=AsyncMock(),
        symbols=["BTCUSDT", "ETHUSDT"],
        max_concurrency=2,
    )
    evaluated: list[str] = []

    async def fake_scan(symbol: str) -> ScanResult:
        return ScanResult(
            symbol=symbol,
            signal_score=9.0,
            direction="long",
            price=100.0,
        )

    async def fake_evaluate(result: ScanResult) -> None:
        evaluated.append(result.symbol)

    monkeypatch.setattr(scanner, "_scan_symbol", fake_scan)
    monkeypatch.setattr(scanner, "_evaluate_trade", fake_evaluate)

    await scanner.scan_once()

    assert evaluated == ["BTCUSDT", "ETHUSDT"]


def test_scan_history_can_be_filtered_by_symbol() -> None:
    scanner = SignalScanner(mcp_client=AsyncMock(), symbols=["BTCUSDT", "ETHUSDT"])
    scanner._add_to_history(ScanResult(symbol="BTCUSDT"))
    scanner._add_to_history(ScanResult(symbol="ETHUSDT"))
    scanner._add_to_history(ScanResult(symbol="BTCUSDT"))

    assert len(scanner.get_scan_history("BTCUSDT")) == 2
    assert len(scanner.get_scan_history("ETHUSDT")) == 1
