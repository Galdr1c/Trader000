"""Tests for the Decision Engine and Risk Management."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from src.decision.risk import RiskManager
from src.decision.position import PositionManager, PositionState, ExitType
from src.decision.engine import DecisionEngine
from src.webhook.models import TVAlertPayload, SignalDirection


class TestRiskManager:
    """Tests for risk management logic."""

    def _rm_with_today(self) -> RiskManager:
        """Create a RiskManager with today's date already set (prevents auto-reset)."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return rm

    def test_initial_can_trade(self):
        rm = RiskManager(initial_equity=100_000)
        can, reason = rm.can_trade()
        assert can is True

    def test_daily_max_loss_blocks_trades(self):
        rm = self._rm_with_today()
        rm.state.daily_pnl = -6000  # -6% of 100k
        can, reason = rm.can_trade()
        assert can is False
        assert "daily_max_loss" in reason

    def test_consecutive_stops_trigger_cooldown(self):
        rm = self._rm_with_today()
        rm.state.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=12)
        can, reason = rm.can_trade()
        assert can is False
        assert "cooldown" in reason

    def test_position_sizing_scales_with_score(self):
        rm = RiskManager(initial_equity=100_000)
        size_high = rm.calculate_position_size(100_000, signal_score=12.0)
        size_low = rm.calculate_position_size(100_000, signal_score=7.0)
        assert size_high > size_low

    def test_position_sizing_reduced_for_high_risk(self):
        rm = RiskManager(initial_equity=100_000)
        size_low = rm.calculate_position_size(100_000, signal_score=10.0, risk_level="low")
        size_high = rm.calculate_position_size(100_000, signal_score=10.0, risk_level="high")
        assert size_low > size_high

    def test_record_stop_increments_counter(self):
        rm = self._rm_with_today()
        rm.record_trade_result(-500, was_stop=True)
        assert rm.state.consecutive_stops == 1
        rm.record_trade_result(-500, was_stop=True)
        assert rm.state.consecutive_stops == 2

    def test_record_non_stop_resets_counter(self):
        rm = self._rm_with_today()
        rm.record_trade_result(-500, was_stop=True)
        rm.record_trade_result(-500, was_stop=True)
        rm.record_trade_result(1000, was_stop=False)
        assert rm.state.consecutive_stops == 0


class TestPositionManager:
    """Tests for position tracking."""

    def test_open_position(self):
        pm = PositionManager()
        pos = pm.open_position("BTC/USDT:USDT", "long", 65000, 9.5, 4.2, 0.1)
        assert pm.has_position is True
        assert pos.side == "long"
        assert pos.entry_price == 65000

    def test_close_position(self):
        pm = PositionManager()
        pm.open_position("BTC/USDT:USDT", "long", 65000, 9.5, 4.2, 0.1)
        result = pm.close_position(ExitType.TP, 67000)
        assert pm.has_position is False
        assert result.exit_type == ExitType.TP
        assert result.pnl_pct > 0

    def test_update_bar_tracks_extremes(self):
        pm = PositionManager()
        pos = pm.open_position("BTC/USDT:USDT", "long", 65000, 9.5, 4.2, 0.1)
        pos.update_bar(high=66000, low=64500, close=65500)
        assert pos.highest_price == 66000
        assert pos.lowest_price == 64500
        assert pos.bars_in_position == 1

    def test_peak_profit_pct(self):
        pm = PositionManager()
        pos = pm.open_position("BTC/USDT:USDT", "long", 100, 9.5, 4.2, 1.0)
        pos.update_bar(high=110, low=99, close=105)
        assert pos.peak_profit_pct() == pytest.approx(10.0, abs=0.01)


class TestWebhookModels:
    """Tests for TradingView alert parsing."""

    def test_parse_long_alert(self):
        text = (
            "🟢 LONG ENTRY\n"
            "Symbol: BTCUSDT\n"
            "Price: 67500.00\n"
            "Signal Score: 9.5/13.5\n"
            "TP Distance: 4.2%\n"
            "ADX Trend: ✅ Strong"
        )
        payload = TVAlertPayload.from_text(text)
        assert payload.direction == SignalDirection.LONG
        assert payload.symbol == "BTCUSDT"
        assert payload.price == 67500.0
        assert payload.signal_score == 9.5

    def test_parse_short_alert(self):
        text = (
            "🔴 SHORT ENTRY\n"
            "Symbol: ETHUSDT\n"
            "Price: 3500.00\n"
            "Signal Score: 8.2/13.5\n"
            "TP Distance: 3.5%\n"
            "ADX Trend: ⚠ Weak"
        )
        payload = TVAlertPayload.from_text(text)
        assert payload.direction == SignalDirection.SHORT
        assert payload.signal_score == 8.2
