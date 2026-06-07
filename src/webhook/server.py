"""FastAPI webhook server — receives TradingView alerts.

Routes an incoming alert through the full pipeline:
    Webhook → Signal Engine → Sentiment → AI Layer → Decision → Order
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import PlainTextResponse

from src.config import settings
from src.monitoring.dashboard import DASHBOARD_HTML
from src.monitoring.system import (
    get_liveness,
    get_prometheus_metrics,
    get_system_status,
    record_alert,
)
from src.webhook.models import TVAlertPayload, WebhookResponse

if TYPE_CHECKING:
    from src.decision.engine import DecisionEngine
    from src.decision.position import PositionManager
    from src.scanner.scanner import SignalScanner

logger = logging.getLogger(__name__)

# These get injected at startup — avoids circular imports
_engine: "DecisionEngine | None" = None
_exchange_client: Any = None
_ai_client: Any = None
_scanner: "SignalScanner | None" = None
_position_manager: "PositionManager | None" = None
# Recent alerts ring buffer for dashboard
_alert_history: deque[dict] = deque(maxlen=50)


def set_engine(engine: "DecisionEngine") -> None:
    """Inject the decision engine at startup."""
    global _engine  # noqa: PLW0603
    _engine = engine


def set_clients(exchange_client: Any = None, ai_client: Any = None) -> None:
    """Inject exchange and AI clients for status monitoring."""
    global _exchange_client, _ai_client  # noqa: PLW0603
    _exchange_client = exchange_client
    _ai_client = ai_client


def set_runtime_state(
    scanner: "SignalScanner | None",
    position_manager: "PositionManager | None",
) -> None:
    """Inject scanner and position state used by dashboard endpoints."""
    global _scanner, _position_manager  # noqa: PLW0603
    _scanner = scanner
    _position_manager = position_manager


def _add_alert(
    symbol: str, direction: str, score: float, action: str,
    ai_conf: int = 0, composite: str = "",
) -> None:
    """Add an alert to the recent history ring buffer."""
    _alert_history.append({
        "time": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "direction": direction,
        "score": score,
        "action": action,
        "ai_confidence": ai_conf,
        "composite": composite,
    })


def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify HMAC signature from TradingView (optional security layer)."""
    if not settings.webhook_secret:
        return True
    expected = hmac.HMAC(
        settings.webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_webhook(
    request: Request,
    x_tv_signature: str = Header(default=""),
) -> WebhookResponse:
    """Main webhook endpoint for TradingView alerts."""
    body = await request.body()

    if settings.webhook_secret and not _verify_signature(body, x_tv_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    content_type = request.headers.get("content-type", "")
    if "json" in content_type:
        try:
            data = await request.json()
            payload = TVAlertPayload(**data)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
    else:
        text = body.decode("utf-8", errors="replace")
        payload = TVAlertPayload.from_text(text)

    if not payload.symbol:
        raise HTTPException(status_code=400, detail="Missing symbol in alert")

    logger.info(
        "webhook_received | symbol=%s direction=%s score=%.1f",
        payload.symbol,
        payload.direction.value,
        payload.signal_score,
    )

    if _engine is None:
        logger.warning("decision_engine_not_initialized — alert ignored")
        _add_alert(payload.symbol, payload.direction.value, payload.signal_score, "ignored")
        return WebhookResponse(
            status="ignored",
            message="Engine not ready",
            symbol=payload.symbol,
            signal_score=payload.signal_score,
        )

    result = await _engine.evaluate_alert(payload)
    record_alert()
    _add_alert(
        payload.symbol, payload.direction.value, payload.signal_score,
        result.get("action", "none"),
        ai_conf=result.get("ai_confidence", 0),
        composite=result.get("composite_decision", ""),
    )

    return WebhookResponse(
        status="ok",
        message=result.get("reason", ""),
        symbol=payload.symbol,
        signal_score=payload.signal_score,
        action_taken=result.get("action", "none"),
    )


async def health() -> dict:
    """Quick liveness check — always fast, no external calls."""
    return get_liveness()


async def status() -> JSONResponse:
    """Detailed system status dashboard."""
    status_data = get_system_status(
        exchange_client=_exchange_client,
        ai_client=_ai_client,
    )
    return JSONResponse(content=status_data.to_dict())


async def metrics() -> PlainTextResponse:
    """Prometheus-compatible metrics endpoint."""
    text = get_prometheus_metrics(
        exchange_client=_exchange_client,
        ai_client=_ai_client,
    )
    return PlainTextResponse(content=text, media_type="text/plain")


async def alerts() -> JSONResponse:
    """Recent webhook alerts for dashboard."""
    return JSONResponse(content=list(_alert_history))


async def scanner_status() -> JSONResponse:
    """Return scanner state and recent results."""
    if _scanner is None:
        return JSONResponse(content={"running": False, "symbols": [], "results": []})
    return JSONResponse(content={
        "running": _scanner.is_running(),
        "symbols": _scanner.symbols,
        "interval_seconds": _scanner.interval_seconds,
        "results": [asdict(result) for result in _scanner.scan_history],
    })


def _latest_prices() -> dict[str, float]:
    prices: dict[str, float] = {}
    if _scanner is None:
        return prices
    for result in _scanner.scan_history:
        if result.price > 0:
            prices[result.symbol] = result.price
    return prices


async def positions() -> JSONResponse:
    """Return active positions and aggregate P&L."""
    if _position_manager is None:
        return JSONResponse(content={
            "positions": [],
            "summary": {
                "active_count": 0,
                "realized_value": 0,
                "unrealized_value": 0,
                "total_value": 0,
            },
        })

    prices = _latest_prices()
    items = []
    for position in _position_manager.active_positions:
        current_price = prices.get(position.symbol)
        unrealized = None
        pnl_pct = None
        if current_price is not None:
            pnl_pct = position.current_pnl_pct(current_price)
            unrealized = position.entry_price * position.quantity * pnl_pct / 100
        items.append({
            "symbol": position.symbol,
            "side": position.side,
            "entry_price": position.entry_price,
            "current_price": current_price,
            "quantity": position.quantity,
            "entry_score": position.entry_score,
            "unrealized_pnl_pct": pnl_pct,
            "unrealized_pnl": unrealized,
        })

    return JSONResponse(content={
        "positions": items,
        "summary": _position_manager.get_pnl_summary(prices),
    })


async def performance() -> JSONResponse:
    """Return realized trades and cumulative P&L series."""
    trades = []
    series = [{"index": 0, "pnl": 0.0}]
    cumulative = 0.0
    if _position_manager is not None:
        for index, position in enumerate(_position_manager.realized_history, start=1):
            pnl_value = position.entry_price * position.initial_qty * position.pnl_pct / 100
            cumulative += pnl_value
            trades.append({
                "symbol": position.symbol,
                "side": position.side,
                "entry_price": position.entry_price,
                "exit_price": position.exit_price,
                "quantity": position.initial_qty,
                "pnl_pct": position.pnl_pct,
                "pnl": pnl_value,
                "exit_type": position.exit_type.value if position.exit_type else None,
            })
            series.append({"index": index, "pnl": cumulative})
    return JSONResponse(content={"trades": trades, "series": series})


async def feed() -> JSONResponse:
    """Live feed: news + sentiment + social media for dashboard.

    Gracefully handles partial failures — if one data source fails,
    others still return. Dashboard never sees a 500.
    """
    from src.sentiment.fear_greed import fetch_fear_greed
    from src.sentiment.news import fetch_crypto_news
    from src.sentiment.social import get_social_health

    fg_result, news_result = await asyncio.gather(
        fetch_fear_greed(),
        fetch_crypto_news(coin="BTC", hours=6),
        return_exceptions=True,
    )

    fg = fg_result if isinstance(fg_result, int) else 50
    news = news_result if isinstance(news_result, list) else []

    return JSONResponse(content={
        "fear_greed": fg,
        "news": news[:15],
        "social_tools": get_social_health(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })


async def dashboard() -> PlainTextResponse:
    """Live monitoring dashboard — open in browser."""
    return PlainTextResponse(content=DASHBOARD_HTML, media_type="text/html")


def create_app(lifespan=None) -> FastAPI:
    """Create the FastAPI app with optional lifespan."""
    _app = FastAPI(title="SVTR Bot Webhook", version="1.0.0", lifespan=lifespan)
    _app.add_api_route("/", dashboard, methods=["GET"])
    _app.add_api_route("/webhook", handle_webhook, methods=["POST"], response_model=WebhookResponse)
    _app.add_api_route("/health", health, methods=["GET"])
    _app.add_api_route("/status", status, methods=["GET"])
    _app.add_api_route("/api/alerts", alerts, methods=["GET"])
    _app.add_api_route("/api/scanner", scanner_status, methods=["GET"])
    _app.add_api_route("/api/positions", positions, methods=["GET"])
    _app.add_api_route("/api/performance", performance, methods=["GET"])
    _app.add_api_route("/api/feed", feed, methods=["GET"])
    _app.add_api_route("/metrics", metrics, methods=["GET"])
    return _app


app = create_app()
