from __future__ import annotations

import pytest

from src.decision.engine import DecisionEngine
from src.decision.position import ExitType, PositionManager
from src.decision.risk import RiskManager
from src.webhook.models import SignalDirection, TVAlertPayload


def _open(
    manager: PositionManager,
    symbol: str,
    side: str = "long",
    price: float = 100.0,
    quantity: float = 1.0,
):
    return manager.open_position(
        symbol=symbol,
        side=side,
        entry_price=price,
        entry_score=9.0,
        dynamic_tp=4.0,
        quantity=quantity,
    )


def test_positions_are_tracked_by_symbol() -> None:
    manager = PositionManager()

    _open(manager, "BTCUSDT")
    _open(manager, "ETHUSDT")

    assert manager.has_position is True
    assert manager.has_position_for("BTCUSDT") is True
    assert manager.has_position_for("ETHUSDT") is True
    assert len(manager.active_positions) == 2


def test_duplicate_symbol_position_is_rejected() -> None:
    manager = PositionManager()
    _open(manager, "BTCUSDT")

    with pytest.raises(ValueError, match="already active"):
        _open(manager, "BTCUSDT")


def test_close_position_only_removes_requested_symbol() -> None:
    manager = PositionManager()
    _open(manager, "BTCUSDT")
    _open(manager, "ETHUSDT")

    closed = manager.close_position(ExitType.TP, 110.0, symbol="BTCUSDT")

    assert closed is not None
    assert closed.symbol == "BTCUSDT"
    assert manager.has_position_for("BTCUSDT") is False
    assert manager.has_position_for("ETHUSDT") is True
    assert manager.realized_history[-1].pnl_pct == pytest.approx(10.0)


def test_unrealized_pnl_summary_aggregates_symbols() -> None:
    manager = PositionManager()
    _open(manager, "BTCUSDT", price=100.0, quantity=2.0)
    _open(manager, "ETHUSDT", side="short", price=200.0, quantity=1.0)

    summary = manager.get_pnl_summary({"BTCUSDT": 110.0, "ETHUSDT": 180.0})

    assert summary["unrealized_value"] == pytest.approx(40.0)
    assert summary["active_count"] == 2


def test_portfolio_risk_rejects_position_count_limit() -> None:
    risk = RiskManager()

    allowed, reason = risk.can_open_position(
        active_count=3,
        current_exposure_pct=30.0,
        new_exposure_pct=10.0,
        max_positions=3,
        max_exposure_pct=80.0,
    )

    assert allowed is False
    assert "max_positions" in reason


def test_portfolio_risk_rejects_total_exposure_limit() -> None:
    risk = RiskManager()

    allowed, reason = risk.can_open_position(
        active_count=1,
        current_exposure_pct=70.0,
        new_exposure_pct=15.0,
        max_positions=3,
        max_exposure_pct=80.0,
    )

    assert allowed is False
    assert "portfolio_exposure" in reason


@pytest.mark.asyncio
async def test_decision_engine_rejects_duplicate_symbol(monkeypatch) -> None:
    manager = PositionManager()
    _open(manager, "BTCUSDT")
    engine = DecisionEngine(RiskManager(), manager)
    monkeypatch.setattr("src.decision.engine.settings.sentiment_enabled", False)

    result = await engine.evaluate_alert(
        TVAlertPayload(
            symbol="BTCUSDT",
            direction=SignalDirection.LONG,
            price=100.0,
            signal_score=9.0,
            tp_distance=4.0,
        )
    )

    assert result["action"] == "none"
    assert "position_already_active" in result["reason"]


@pytest.mark.asyncio
async def test_decision_engine_rejects_portfolio_position_limit(monkeypatch) -> None:
    manager = PositionManager()
    _open(manager, "ETHUSDT")
    engine = DecisionEngine(RiskManager(), manager)
    monkeypatch.setattr("src.decision.engine.settings.sentiment_enabled", False)
    monkeypatch.setattr("src.decision.engine.settings.max_active_positions", 1)

    result = await engine.evaluate_alert(
        TVAlertPayload(
            symbol="BTCUSDT",
            direction=SignalDirection.LONG,
            price=100.0,
            signal_score=9.0,
            tp_distance=4.0,
        )
    )

    assert result["action"] == "none"
    assert "max_positions" in result["reason"]
