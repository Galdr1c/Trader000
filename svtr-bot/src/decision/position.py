"""Position management — TP/SL lifecycle tracking."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ExitType(str, Enum):
    TP = "tp"
    BULK_TP = "bulk_tp"
    STOP = "stop"
    TRAILING = "trailing"
    VWAP_EXIT = "vwap_exit"
    MAX_LOSS = "max_loss"
    SIGNAL_DROP = "signal_drop"
    TIME_DECAY = "time_decay"
    AUTO_CLOSE = "auto_close"
    MANUAL = "manual"


@dataclass
class PositionState:
    """Tracks the lifecycle of a single position."""

    symbol: str
    side: str  # "long" or "short"
    entry_price: float
    entry_score: float
    dynamic_tp: float  # TP distance in %
    quantity: float
    entry_bar_index: int = 0
    bars_in_position: int = 0
    chunks_taken: int = 0
    initial_qty: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = float("inf")
    stop_price: float = 0.0
    max_loss_price: float = 0.0
    is_active: bool = True
    exit_type: ExitType | None = None
    exit_price: float = 0.0
    pnl_pct: float = 0.0

    def update_bar(self, high: float, low: float, close: float) -> None:
        """Update position state with new bar data."""
        self.bars_in_position += 1
        if high > self.highest_price:
            self.highest_price = high
        if low < self.lowest_price:
            self.lowest_price = low

    def current_pnl_pct(self, current_price: float) -> float:
        """Calculate current unrealized P&L percentage."""
        if self.side == "long":
            return (current_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - current_price) / self.entry_price * 100

    def peak_profit_pct(self) -> float:
        """Calculate the maximum unrealized profit from entry in %."""
        if self.side == "long":
            return (self.highest_price - self.entry_price) / self.entry_price * 100
        return (self.entry_price - self.lowest_price) / self.entry_price * 100

    def pullback_from_peak(self) -> float:
        """Calculate how far price has pulled back from peak in %."""
        if self.side == "long" and self.highest_price > self.entry_price:
            return (self.highest_price - self.entry_price) / self.entry_price * 100
        elif self.side == "short" and self.lowest_price < self.entry_price:
            return (self.entry_price - self.lowest_price) / self.entry_price * 100
        return 0.0

    def close(self, exit_type: ExitType, exit_price: float) -> None:
        """Close the position."""
        self.is_active = False
        self.exit_type = exit_type
        self.exit_price = exit_price
        self.pnl_pct = self.current_pnl_pct(exit_price)
        logger.info(
            "position_closed | %s %s | exit=%s | pnl=%.2f%%",
            self.side,
            self.symbol,
            exit_type.value,
            self.pnl_pct,
        )


class PositionManager:
    """Manages active position state and TP/SL lifecycle."""

    def __init__(self) -> None:
        self.active: PositionState | None = None

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        entry_score: float,
        dynamic_tp: float,
        quantity: float,
        stop_price: float = 0.0,
        max_loss_price: float = 0.0,
    ) -> PositionState:
        """Open a new tracked position."""
        self.active = PositionState(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            entry_score=entry_score,
            dynamic_tp=dynamic_tp,
            quantity=quantity,
            initial_qty=quantity,
            highest_price=entry_price,
            lowest_price=entry_price,
            stop_price=stop_price,
            max_loss_price=max_loss_price,
        )
        logger.info(
            "position_opened | %s %s | entry=%.2f | score=%.1f | tp=%.1f%%",
            side,
            symbol,
            entry_price,
            entry_score,
            dynamic_tp,
        )
        return self.active

    def close_position(
        self, exit_type: ExitType, exit_price: float
    ) -> PositionState | None:
        """Close the active position and return its final state."""
        if not self.active:
            return None
        self.active.close(exit_type, exit_price)
        result = self.active
        self.active = None
        return result

    @property
    def has_position(self) -> bool:
        return self.active is not None and self.active.is_active
