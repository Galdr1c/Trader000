"""Position management — TP/SL lifecycle tracking."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
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
        self._active: dict[str, PositionState] = {}
        self._realized: deque[PositionState] = deque(maxlen=200)

    @property
    def active(self) -> PositionState | None:
        """Return the first active position for legacy single-symbol callers."""
        return next(iter(self._active.values()), None)

    @property
    def active_positions(self) -> list[PositionState]:
        return list(self._active.values())

    @property
    def realized_history(self) -> list[PositionState]:
        return list(self._realized)

    def get_position(self, symbol: str) -> PositionState | None:
        return self._active.get(symbol)

    def has_position_for(self, symbol: str) -> bool:
        position = self.get_position(symbol)
        return position is not None and position.is_active

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
        if self.has_position_for(symbol):
            raise ValueError(f"position already active for {symbol}")

        position = PositionState(
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
        self._active[symbol] = position
        logger.info(
            "position_opened | %s %s | entry=%.2f | score=%.1f | tp=%.1f%%",
            side,
            symbol,
            entry_price,
            entry_score,
            dynamic_tp,
        )
        return position

    def close_position(
        self,
        exit_type: ExitType,
        exit_price: float,
        symbol: str | None = None,
    ) -> PositionState | None:
        """Close the active position and return its final state."""
        if symbol is None:
            position = self.active
            symbol = position.symbol if position else None
        else:
            position = self.get_position(symbol)
        if position is None or symbol is None:
            return None
        position.close(exit_type, exit_price)
        del self._active[symbol]
        self._realized.append(position)
        return position

    def get_pnl_summary(self, prices: dict[str, float]) -> dict[str, float | int]:
        """Calculate aggregate realized and unrealized P&L values."""
        unrealized_value = 0.0
        for symbol, position in self._active.items():
            current_price = prices.get(symbol)
            if current_price is None:
                continue
            notional = position.entry_price * position.quantity
            unrealized_value += notional * position.current_pnl_pct(current_price) / 100

        realized_value = sum(
            position.entry_price * position.initial_qty * position.pnl_pct / 100
            for position in self._realized
        )
        return {
            "active_count": len(self._active),
            "realized_value": realized_value,
            "unrealized_value": unrealized_value,
            "total_value": realized_value + unrealized_value,
        }

    @property
    def has_position(self) -> bool:
        return any(position.is_active for position in self._active.values())
