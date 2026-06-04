"""Tests for Circuit Breaker and Risk Management (Phase 4).

Covers: daily loss limits, consecutive stop detection, cooldown periods,
position sizing under different risk levels, and edge cases.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from src.decision.risk import RiskManager, RiskState


class TestRiskManager:
    """Test suite for RiskManager circuit breaker logic."""

    def test_initial_state_can_trade(self):
        """Fresh RiskManager allows trading."""
        rm = RiskManager(initial_equity=100_000)
        can, reason = rm.can_trade()
        assert can is True
        assert reason == "ok"

    def test_daily_max_loss_blocks_trades(self):
        """Exceeding daily max loss blocks new trades."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rm.state.daily_pnl = -6000  # -6% of 100k
        can, reason = rm.can_trade()
        assert can is False
        assert "daily_max_loss" in reason

    def test_daily_max_loss_near_limit_allows(self):
        """Below daily max loss limit allows trading."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rm.state.daily_pnl = -4000  # -4% of 100k (limit is 5%)
        can, reason = rm.can_trade()
        assert can is True

    def test_consecutive_stops_blocks(self):
        """3+ consecutive stops triggers circuit breaker."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rm.state.consecutive_stops = 3
        can, reason = rm.can_trade()
        assert can is False
        assert "consecutive_stops" in reason

    def test_cooldown_blocks_trades(self):
        """Active cooldown period blocks trading."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rm.state.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=12)
        can, reason = rm.can_trade()
        assert can is False
        assert "cooldown" in reason

    def test_cooldown_expired_allows(self):
        """Expired cooldown allows trading again."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rm.state.cooldown_until = datetime.now(timezone.utc) - timedelta(hours=1)
        can, reason = rm.can_trade()
        assert can is True

    def test_daily_reset_clears_state(self):
        """New day resets daily PnL and trade count."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = "2020-01-01"
        rm.state.daily_pnl = -5000
        rm.state.trades_today = 10
        rm.state.consecutive_stops = 2

        rm.check_daily_reset()

        assert rm.state.daily_pnl == 0.0
        assert rm.state.trades_today == 0
        assert rm.state.consecutive_stops == 0

    def test_non_stop_exit_resets_consecutive(self):
        """A winning/TP exit resets consecutive stop counter."""
        rm = RiskManager(initial_equity=100_000)
        rm.state.consecutive_stops = 2
        rm.record_trade_result(pnl=500, was_stop=False)
        assert rm.state.consecutive_stops == 0

    def test_stop_exit_increments_counter(self):
        """A stop loss exit increments the counter."""
        rm = RiskManager(initial_equity=100_000)
        rm.record_trade_result(pnl=-200, was_stop=True)
        assert rm.state.consecutive_stops == 1

    def test_circuit_breaker_activates_cooldown(self):
        """Reaching stop limit activates cooldown."""
        rm = RiskManager(initial_equity=100_000)
        rm._last_reset_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rm.state.consecutive_stops = 2  # one more stop triggers it (limit is 3)
        rm.record_trade_result(pnl=-100, was_stop=True)
        # Now consecutive_stops = 3 = limit, cooldown should be active
        assert rm.state.cooldown_until is not None
        assert rm.state.cooldown_until > datetime.now(timezone.utc)


class TestPositionSizing:
    """Test suite for position size calculation."""

    def test_base_position_size(self):
        """Standard signal gets base position size."""
        rm = RiskManager(initial_equity=100_000)
        pct = rm.calculate_position_size(100_000, signal_score=8.0, risk_level="medium")
        assert 1.0 <= pct <= 25.0

    def test_strong_signal_larger_position(self):
        """Higher signal score → larger position."""
        rm = RiskManager(initial_equity=100_000)
        weak = rm.calculate_position_size(100_000, signal_score=7.0)
        strong = rm.calculate_position_size(100_000, signal_score=12.0)
        assert strong >= weak

    def test_high_risk_smaller_position(self):
        """High risk → smaller position."""
        rm = RiskManager(initial_equity=100_000)
        low = rm.calculate_position_size(100_000, signal_score=10.0, risk_level="low")
        high = rm.calculate_position_size(100_000, signal_score=10.0, risk_level="high")
        assert high < low

    def test_position_size_clamped(self):
        """Position size never exceeds 25% or goes below 1%."""
        rm = RiskManager(initial_equity=100_000)
        # Extreme case
        pct = rm.calculate_position_size(100_000, signal_score=13.5, risk_level="low")
        assert pct <= 25.0
        assert pct >= 1.0


class TestEdgeCases:
    """Edge case tests for risk management."""

    def test_zero_equity(self):
        """Zero equity doesn't crash."""
        rm = RiskManager(initial_equity=0)
        pct = rm.calculate_position_size(0, signal_score=8.0)
        assert pct >= 1.0  # Minimum position size

    def test_negative_pnl(self):
        """Negative PnL is tracked correctly."""
        rm = RiskManager(initial_equity=100_000)
        rm.record_trade_result(pnl=-500, was_stop=True)
        assert rm.state.daily_pnl == -500

    def test_multiple_wins_accumulate(self):
        """Multiple winning trades accumulate PnL."""
        rm = RiskManager(initial_equity=100_000)
        rm.record_trade_result(pnl=200, was_stop=False)
        rm.record_trade_result(pnl=300, was_stop=False)
        assert rm.state.daily_pnl == 500
        assert rm.state.trades_today == 2
