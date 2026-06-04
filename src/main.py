"""SVTR Bot — main entry point.

Starts the FastAPI webhook server, initializes all components,
and runs the background scheduler.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.config import settings
from src.monitoring.logger import setup_logging
from src.decision.engine import DecisionEngine
from src.decision.risk import RiskManager
from src.decision.position import PositionManager
from src.webhook.server import create_app, set_engine, set_clients
from src.monitoring.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

# ── Shared singletons ────────────────────────────────────────────────
risk_manager = RiskManager()
position_manager = PositionManager()
telegram = TelegramNotifier()
ai_client = None
exchange_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global ai_client, exchange_client  # noqa: PLW0603

    setup_logging()
    logger.info("svtr_bot_starting | version=1.0.0")

    # ── Initialize Exchange ──────────────────────────────────────
    if settings.exchange_api_key:
        try:
            from src.exchange.client import ExchangeClient

            exchange_client = ExchangeClient()
            await exchange_client.initialize()
            logger.info("exchange_connected | %s", settings.exchange_id)
        except Exception as e:
            logger.error("exchange_init_error | %s", e)

    # ── Initialize AI ────────────────────────────────────────────
    if settings.ai_enabled and settings.anthropic_api_key:
        try:
            from src.ai_layer.claude_client import ClaudeClient

            ai_client = ClaudeClient()
            logger.info("ai_client_initialized | model=%s", settings.anthropic_model)
        except Exception as e:
            logger.error("ai_init_error | %s", e)

    # ── Create Decision Engine ───────────────────────────────────
    engine = DecisionEngine(
        risk_manager=risk_manager,
        position_manager=position_manager,
        ai_client=ai_client,
        exchange_client=exchange_client,
        telegram=telegram,
    )
    set_engine(engine)
    set_clients(exchange_client=exchange_client, ai_client=ai_client)

    logger.info(
        "svtr_bot_ready | exchange=%s | ai=%s | symbol=%s | tf=%s | min_score=%.1f",
        settings.exchange_id,
        settings.ai_enabled,
        settings.trading_symbol,
        settings.timeframe.value,
        settings.min_signal_score,
    )

    await telegram.send_status(
        f"🚀 <b>SVTR Bot Started</b>\n"
        f"Exchange: {settings.exchange_id}{' (testnet)' if settings.exchange_testnet else ''}\n"
        f"Symbol: {settings.trading_symbol}\n"
        f"Timeframe: {settings.timeframe.value}\n"
        f"Min Score: {settings.min_signal_score}\n"
        f"AI: {'ON' if settings.ai_enabled and ai_client else 'OFF'}\n"
        f"Sentiment: {'ON' if settings.sentiment_enabled else 'OFF'}"
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("svtr_bot_shutting_down")
    if exchange_client:
        await exchange_client.close()
    await telegram.send_status("🛑 <b>SVTR Bot Stopped</b>")


# Create the app with lifespan
app = create_app(lifespan=lifespan)


def main() -> None:
    """Run the webhook server."""
    uvicorn.run(
        "src.main:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
