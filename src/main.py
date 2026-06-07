"""SVTR Bot — main entry point.

Two data source modes:
1. MCP Scanner (default) — periodically fetches market data via tradingview-mcp
2. Webhook Server (fallback) — receives TradingView alerts via HTTP POST

The MCP scanner runs as a background task while the webhook server
provides the dashboard, health/status endpoints, and monitoring.
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
from src.mcp_provider.client import MCPClient
from src.scanner.scanner import SignalScanner

logger = logging.getLogger(__name__)

# ── Shared singletons ────────────────────────────────────────────────
risk_manager = RiskManager()
position_manager = PositionManager()
telegram = TelegramNotifier()
ai_client = None
exchange_client = None
mcp_client: MCPClient | None = None
scanner: SignalScanner | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global ai_client, exchange_client, mcp_client, scanner  # noqa: PLW0603

    setup_logging()
    logger.info("svtr_bot_starting | version=1.0.0")

    # ── Initialize MCP Client (tradingview-mcp) ──────────────────
    mcp_client = MCPClient(cache_ttl=settings.mcp_cache_ttl)
    logger.info("mcp_client_initialized")

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
    # ── Initialize AI & TradingAgents ────────────────────────────
    ta_client = None
    if settings.ai_enabled and settings.anthropic_api_key:
        try:
            from src.ai_layer.claude_client import ClaudeClient

            ai_client = ClaudeClient()
            logger.info("ai_client_initialized | model=%s", settings.anthropic_model)
        except Exception as e:
            logger.error("ai_init_error | %s", e)

    if settings.anthropic_api_key:
        try:
            from src.ai_layer.trading_agents import TradingAgentsDecisionClient

            ta_client = TradingAgentsDecisionClient(
                anthropic_api_key=settings.anthropic_api_key,
                deep_think_model=settings.anthropic_model,
                quick_think_model=settings.anthropic_model,
            )
            logger.info("trading_agents_initialized | model=%s", settings.anthropic_model)
        except Exception as e:
            logger.error("trading_agents_init_error | %s", e)

    # ── Create Decision Engine ───────────────────────────────────
    engine = DecisionEngine(
        risk_manager=risk_manager,
        position_manager=position_manager,
        ai_client=ai_client,
        exchange_client=exchange_client,
        telegram=telegram,
        trading_agents_client=ta_client,
    )
    set_engine(engine)
    set_clients(exchange_client=exchange_client, ai_client=ai_client)

    # ── Initialize MCP Signal Scanner ────────────────────────────
    scan_interval = settings.scan_interval_seconds
    scanner = SignalScanner(
        mcp_client=mcp_client,
        decision_engine=engine,
        interval_seconds=scan_interval,
        symbols=settings.parsed_trading_symbols,
        max_concurrency=settings.max_concurrent_scans,
    )
    await scanner.start()
    logger.info(
        "scanner_started | interval=%ds | symbols=%s",
        scan_interval,
        scanner.symbols,
    )

    logger.info(
        "svtr_bot_ready | exchange=%s | ai=%s | mcp=on | symbol=%s | tf=%s | min_score=%.1f | scan_interval=%ds",
        settings.exchange_id,
        settings.ai_enabled,
        settings.trading_symbol,
        settings.timeframe.value,
        settings.min_signal_score,
        settings.scan_interval_seconds,
    )

    await telegram.send_status(
        f"🚀 <b>SVTR Bot Started</b>\n"
        f"Mode: <b>MCP Scanner</b> (no webhooks needed)\n"
        f"Exchange: {settings.exchange_id}{' (testnet)' if settings.exchange_testnet else ''}\n"
        f"Symbol: {settings.trading_symbol}\n"
        f"Timeframe: {settings.timeframe.value}\n"
        f"Scan Interval: {settings.scan_interval_seconds}s\n"
        f"Min Score: {settings.min_signal_score}\n"
        f"AI: {'ON' if settings.ai_enabled and ai_client else 'OFF'}\n"
        f"Sentiment: {'ON' if settings.sentiment_enabled else 'OFF'}\n"
        f"Dashboard: http://localhost:{settings.webhook_port}"
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("svtr_bot_shutting_down")
    if scanner:
        await scanner.stop()
    if exchange_client:
        await exchange_client.close()
    await telegram.send_status("🛑 <b>SVTR Bot Stopped</b>")


# Create the app with lifespan
app = create_app(lifespan=lifespan)


def main() -> None:
    """Run the webhook server with MCP scanner."""
    uvicorn.run(
        "src.main:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
