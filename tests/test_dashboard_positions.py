from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.decision.position import ExitType, PositionManager
from src.scanner.scanner import ScanResult, SignalScanner
from src.webhook.server import create_app, set_runtime_state


async def _get(path: str):
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_positions_endpoint_returns_empty_summary() -> None:
    set_runtime_state(scanner=None, position_manager=PositionManager())

    response = await _get("/api/positions")

    assert response.status_code == 200
    assert response.json() == {
        "positions": [],
        "summary": {
            "active_count": 0,
            "realized_value": 0,
            "unrealized_value": 0,
            "total_value": 0,
        },
    }


@pytest.mark.asyncio
async def test_positions_endpoint_uses_latest_scanner_price() -> None:
    scanner = SignalScanner(AsyncMock(), symbols=["BTCUSDT"])
    scanner._add_to_history(ScanResult(symbol="BTCUSDT", price=110.0))
    manager = PositionManager()
    manager.open_position("BTCUSDT", "long", 100.0, 9.0, 4.0, 2.0)
    set_runtime_state(scanner=scanner, position_manager=manager)

    response = await _get("/api/positions")
    body = response.json()

    assert body["positions"][0]["symbol"] == "BTCUSDT"
    assert body["positions"][0]["current_price"] == 110.0
    assert body["positions"][0]["unrealized_pnl"] == pytest.approx(20.0)
    assert body["summary"]["unrealized_value"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_positions_endpoint_marks_missing_price_unavailable() -> None:
    manager = PositionManager()
    manager.open_position("BTCUSDT", "long", 100.0, 9.0, 4.0, 2.0)
    set_runtime_state(scanner=None, position_manager=manager)

    response = await _get("/api/positions")
    position = response.json()["positions"][0]

    assert position["current_price"] is None
    assert position["unrealized_pnl"] is None


@pytest.mark.asyncio
async def test_scanner_endpoint_returns_status_and_results() -> None:
    scanner = SignalScanner(AsyncMock(), symbols=["BTCUSDT", "ETHUSDT"])
    scanner._add_to_history(ScanResult(symbol="BTCUSDT", signal_score=9.0))
    set_runtime_state(scanner=scanner, position_manager=PositionManager())

    response = await _get("/api/scanner")
    body = response.json()

    assert body["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert body["results"][0]["signal_score"] == 9.0


@pytest.mark.asyncio
async def test_performance_endpoint_returns_realized_trades() -> None:
    manager = PositionManager()
    manager.open_position("BTCUSDT", "long", 100.0, 9.0, 4.0, 2.0)
    manager.close_position(ExitType.TP, 110.0, symbol="BTCUSDT")
    set_runtime_state(scanner=None, position_manager=manager)

    response = await _get("/api/performance")
    body = response.json()

    assert body["trades"][0]["symbol"] == "BTCUSDT"
    assert body["trades"][0]["pnl_pct"] == pytest.approx(10.0)
    assert body["series"][-1]["pnl"] == pytest.approx(20.0)


@pytest.mark.asyncio
async def test_dashboard_contains_position_and_performance_views() -> None:
    response = await _get("/")

    assert 'id="positionBody"' in response.text
    assert 'id="pnlChart"' in response.text
    assert "fetchPortfolio" in response.text
