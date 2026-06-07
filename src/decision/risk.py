"""Risk management — circuit breaker, position sizing, daily loss limits."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """Tracks daily risk metrics."""

    daily_pnl: float = 0.0
    consecutive_stops: int = 0
    last_stop_time: datetime | None = None
    cooldown_until: datetime | None = None
    trades_today: int = 0
    peak_equity: float = 0.0

    def reset_daily(self) -> None:
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.consecutive_stops = 0


class RiskManager:
    """Enforces risk limits before allowing new trades."""

    def __init__(self, initial_equity: float = 100_000.0) -> None:
        self.state = RiskState()
        self.initial_equity = initial_equity
        self._last_reset_date: str = ""

    def check_daily_reset(self) -> None:
        """Reset daily counters at midnight UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self.state.reset_daily()
            self._last_reset_date = today
            logger.info("risk_daily_reset | date=%s", today)

    def can_trade(self) -> tuple[bool, str]:
        """Check if we're allowed to open a new position.

        Returns (allowed, reason).
        """
        self.check_daily_reset()

        now = datetime.now(timezone.utc)

        # Cooldown check
        if self.state.cooldown_until and now < self.state.cooldown_until:
            remaining = (self.state.cooldown_until - now).total_seconds() / 3600
            return False, f"cooldown_active | {remaining:.1f}h remaining"

        # Daily max loss check
        if self.state.daily_pnl < 0:
            loss_pct = abs(self.state.daily_pnl) / self.initial_equity * 100
            if loss_pct >= settings.daily_max_loss_pct:
                return False, f"daily_max_loss_reached | -{loss_pct:.1f}%"

        # Consecutive stop check
        if self.state.consecutive_stops >= settings.consecutive_stop_limit:
            return False, f"consecutive_stops | {self.state.consecutive_stops} stops hit"

        return True, "ok"

    def calculate_position_size(
        self,
        equity: float,
        signal_score: float,
        risk_level: str = "medium",
    ) -> float:
        """Calculate position size as percentage of equity.

        Adjusts based on signal strength and AI risk assessment.
        """
        base_pct = settings.position_size_pct  # e.g. 20%

        # Score adjustment: stronger signal → slightly larger
        score_factor = min(1.2, max(0.5, signal_score / 10.0))

        # Risk level adjustment
        risk_factor = {"low": 1.0, "medium": 0.7, "high": 0.4}.get(risk_level, 0.5)

        adjusted_pct = base_pct * score_factor * risk_factor
        return round(max(1.0, min(25.0, adjusted_pct)), 2)

    def can_open_position(
        self,
        active_count: int,
        current_exposure_pct: float,
        new_exposure_pct: float,
        max_positions: int,
        max_exposure_pct: float,
    ) -> tuple[bool, str]:
        """Check portfolio-level position count and exposure limits."""
        if active_count >= max_positions:
            return False, f"max_positions_reached | {active_count}/{max_positions}"
        total_exposure = current_exposure_pct + new_exposure_pct
        if total_exposure > max_exposure_pct:
            return False, (
                f"portfolio_exposure_exceeded | "
                f"{total_exposure:.1f}% > {max_exposure_pct:.1f}%"
            )
        return True, "ok"

    def record_trade_result(self, pnl: float, was_stop: bool = False) -> None:
        """Record the result of a completed trade."""
        self.check_daily_reset()
        self.state.daily_pnl += pnl
        self.state.trades_today += 1

        if was_stop:
            self.state.consecutive_stops += 1
            self.state.last_stop_time = datetime.now(timezone.utc)

            if self.state.consecutive_stops >= settings.consecutive_stop_limit:
                from datetime import timedelta

                self.state.cooldown_until = datetime.now(timezone.utc) + timedelta(
                    hours=settings.cooldown_hours
                )
                logger.warning(
                    "circuit_breaker_activated | stops=%d | cooldown_until=%s",
                    self.state.consecutive_stops,
                    self.state.cooldown_until.isoformat(),
                )
        else:
            self.state.consecutive_stops = 0  # Reset on non-stop exit

        logger.info(
            "trade_recorded | pnl=%.2f | was_stop=%s | daily_pnl=%.2f | trades=%d",
            pnl,
            was_stop,
            self.state.daily_pnl,
            self.state.trades_today,
        )
