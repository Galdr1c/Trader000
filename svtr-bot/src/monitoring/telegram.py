"""Telegram notification bot for trading alerts."""

from __future__ import annotations

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends trading alerts via Telegram Bot API."""

    def __init__(self) -> None:
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_chat_id
        self._base_url = f"https://api.telegram.org/bot{self._token}"
        self._enabled = bool(self._token and self._chat_id)

    async def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured Telegram chat."""
        if not self._enabled:
            logger.debug("telegram_disabled")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url}/sendMessage",
                    json={
                        "chat_id": self._chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                    },
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error("telegram_send_error | %s", e)
            return False

    async def send_entry_alert(
        self, symbol: str, side: str, price: float, score: float, tp_distance: float
    ) -> None:
        """Send trade entry notification."""
        emoji = "🟢" if side == "long" else "🔴"
        msg = (
            f"{emoji} <b>{side.upper()} ENTRY</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📊 Symbol: <b>{symbol}</b>\n"
            f"💰 Price: <code>{price:,.2f}</code>\n"
            f"⚡ Score: <b>{score:.1f}/13.5</b>\n"
            f"🎯 TP Distance: <b>{tp_distance:.1f}%</b>\n"
            f"━━━━━━━━━━━━━━━━━"
        )
        await self.send(msg)

    async def send_exit_alert(
        self, symbol: str, side: str, exit_type: str, pnl_pct: float
    ) -> None:
        """Send trade exit notification."""
        emoji = "✅" if pnl_pct >= 0 else "❌"
        msg = (
            f"{emoji} <b>{side.upper()} EXIT ({exit_type})</b>\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📊 Symbol: <b>{symbol}</b>\n"
            f"📈 P&L: <b>{pnl_pct:+.2f}%</b>\n"
            f"━━━━━━━━━━━━━━━━━"
        )
        await self.send(msg)

    async def send_error(self, message: str) -> None:
        """Send error alert."""
        msg = f"⚠️ <b>SVTR BOT ERROR</b>\n<pre>{message}</pre>"
        await self.send(msg)

    async def send_status(self, message: str) -> None:
        """Send general status update."""
        msg = f"ℹ️ <b>SVTR BOT</b>\n{message}"
        await self.send(msg)
