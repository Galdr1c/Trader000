"""Shared stop and maximum-loss price calculations."""

from __future__ import annotations


def calculate_stop_prices(
    *,
    price: float,
    direction: str,
    atr_multiplier: float,
    max_loss_pct: float,
) -> tuple[float, float]:
    """Return strategy stop and hard maximum-loss prices."""
    stop_distance_pct = atr_multiplier * 0.02
    if direction == "long":
        return (
            price * (1 - stop_distance_pct),
            price * (1 - max_loss_pct / 100),
        )
    return (
        price * (1 + stop_distance_pct),
        price * (1 + max_loss_pct / 100),
    )
