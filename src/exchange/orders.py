"""Order management — market/limit orders with TP/SL."""

from __future__ import annotations

import logging
from typing import Any

from src.exchange.client import ExchangeClient

logger = logging.getLogger(__name__)


class OrderManager:
    """Handles order placement and lifecycle."""

    def __init__(self, client: ExchangeClient) -> None:
        self.client = client

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> dict[str, Any]:
        """Place a market order.

        Parameters
        ----------
        symbol : str
            Trading pair, e.g. "BTC/USDT:USDT"
        side : str
            "long" or "short"
        quantity : float
            Position size in contracts/base units.
        """
        order_side = "buy" if side == "long" else "sell"

        logger.info(
            "placing_market_order | %s %s | qty=%.6f",
            order_side,
            symbol,
            quantity,
        )

        order = await self.client.exchange.create_market_order(
            symbol=symbol,
            side=order_side,
            amount=quantity,
        )

        logger.info(
            "order_placed | id=%s | %s %s | qty=%.6f | avg_price=%.2f",
            order.get("id", "?"),
            order_side,
            symbol,
            quantity,
            float(order.get("average", 0)),
        )
        return order

    async def place_tp_sl_orders(
        self,
        symbol: str,
        side: str,
        quantity: float,
        tp_price: float,
        sl_price: float,
    ) -> dict[str, Any]:
        """Place take-profit and stop-loss limit orders."""
        close_side = "sell" if side == "long" else "buy"
        results = {}

        # TP order
        try:
            tp_order = await self.client.exchange.create_order(
                symbol=symbol,
                type="limit",
                side=close_side,
                amount=quantity,
                price=tp_price,
                params={"reduceOnly": True, "timeInForce": "GTC"},
            )
            results["tp"] = tp_order
            logger.info("tp_order_placed | price=%.2f | qty=%.6f", tp_price, quantity)
        except Exception as e:
            logger.error("tp_order_error | %s", e)

        # SL order
        try:
            sl_order = await self.client.exchange.create_order(
                symbol=symbol,
                type="stop_market",
                side=close_side,
                amount=quantity,
                params={
                    "stopPrice": sl_price,
                    "reduceOnly": True,
                },
            )
            results["sl"] = sl_order
            logger.info("sl_order_placed | price=%.2f | qty=%.6f", sl_price, quantity)
        except Exception as e:
            logger.error("sl_order_error | %s", e)

        return results

    async def close_position(self, symbol: str, side: str, quantity: float) -> dict:
        """Close an open position with a market order."""
        close_side = "sell" if side == "long" else "buy"

        order = await self.client.exchange.create_market_order(
            symbol=symbol,
            side=close_side,
            amount=quantity,
            params={"reduceOnly": True},
        )

        logger.info("position_closed_market | %s %s | qty=%.6f", close_side, symbol, quantity)
        return order
