"""FastAPI webhook server — receives TradingView alerts.

Routes an incoming alert through the full pipeline:
    Webhook → Signal Engine → Sentiment → AI Layer → Decision → Order
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import PlainTextResponse

from src.config import settings
from src.monitoring.dashboard import DASHBOARD_HTML
from src.monitoring.system import get_system_status, get_liveness, get_prometheus_metrics, record_alert
from src.webhook.models import TVAlertPayload, WebhookResponse

if TYPE_CHECKING:
    from src.decision.engine import DecisionEngine

logger = logging.getLogger(__name__)

# These get injected at startup — avoids circular imports
_engine: "DecisionEngine | None" = None
_exchange_client: Any = None
_ai_client: Any = None
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
    _app.add_api_route("/metrics", metrics, methods=["GET"])
    return _app


app = create_app()
