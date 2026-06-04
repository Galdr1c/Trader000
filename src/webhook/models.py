"""Data models for TradingView webhook payloads.

Supports both JSON and plain-text alert formats from TradingView.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class TVAlertPayload(BaseModel):
    """TradingView alert webhook payload.

    TradingView can send alerts as JSON or as formatted text.
    This model handles both cases.
    """

    symbol: str = Field(default="", description="Trading pair, e.g. BTCUSDT")
    direction: SignalDirection = Field(default=SignalDirection.LONG)
    price: float = Field(default=0.0)
    signal_score: float = Field(default=0.0, ge=0, le=13.5)
    tp_distance: float = Field(default=5.0, description="TP distance in %")
    adx_trend: str = Field(default="weak", description="'strong' or 'weak'")
    message: str = Field(default="", description="Raw alert message")

    @classmethod
    def from_text(cls, text: str) -> "TVAlertPayload":
        """Parse a plain-text TradingView alert message.

        Expected format (from Pine Script alert() calls):
            🟢 LONG ENTRY
            Symbol: BTCUSDT
            Price: 67500.00
            Signal Score: 9.5/13.5
            TP Distance: 4.2%
            ADX Trend: ✅ Strong
        """
        lines = text.strip().split("\n")
        first_line = lines[0].strip() if lines else ""

        # Detect direction
        direction = SignalDirection.LONG
        if "SHORT" in first_line.upper() or "🔴" in first_line:
            direction = SignalDirection.SHORT
        elif "LONG" in first_line.upper() or "🟢" in first_line:
            direction = SignalDirection.LONG

        # Parse key-value pairs
        data: dict[str, Any] = {"direction": direction, "message": text}
        for line in lines:
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                if key == "symbol":
                    data["symbol"] = val
                elif key in ("price", "entry_price"):
                    try:
                        data["price"] = float(val)
                    except ValueError:
                        pass
                elif key in ("signal_score", "score"):
                    try:
                        data["signal_score"] = float(val.split("/")[0])
                    except (ValueError, IndexError):
                        pass
                elif key in ("tp_distance", "tp_%"):
                    try:
                        data["tp_distance"] = float(val.replace("%", ""))
                    except ValueError:
                        pass
                elif "adx" in key or "trend" in key:
                    data["adx_trend"] = "strong" if "strong" in val.lower() or "✅" in val else "weak"

        return cls(**data)


class WebhookResponse(BaseModel):
    """Response sent back to TradingView after processing an alert."""

    status: str = "ok"
    message: str = ""
    symbol: str = ""
    signal_score: float = 0.0
    action_taken: str = "none"
