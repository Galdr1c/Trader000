"""System monitoring — health checks, status dashboard, metrics.

Provides real-time system health visibility:
- /health  → liveness check (quick)
- /status  → detailed system dashboard
- /metrics → Prometheus-compatible metrics

All data is collected without blocking — each check has timeouts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.config import settings
from src.sentiment.social import get_social_health


@dataclass
class SystemStatus:
    """Real-time system health snapshot."""

    # ── Infrastructure ────────────────────────────────────────
    exchange_connected: bool = False
    exchange_id: str = ""
    exchange_testnet: bool = True
    ai_enabled: bool = False
    ai_model: str = ""

    # ── Social / Agent-Reach ──────────────────────────────────
    social_tools: dict[str, bool] = field(default_factory=dict)

    # ── Strategy ──────────────────────────────────────────────
    symbol: str = ""
    timeframe: str = ""
    min_score: float = 0.0

    # ── Runtime ───────────────────────────────────────────────
    uptime_seconds: float = 0.0
    webhook_port: int = 0
    sentiment_enabled: bool = True
    last_alert_time: str = ""
    alerts_processed: int = 0

    # ── Timestamps ────────────────────────────────────────────
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "exchange": {
                "connected": self.exchange_connected,
                "id": self.exchange_id,
                "testnet": self.exchange_testnet,
            },
            "ai": {
                "enabled": self.ai_enabled,
                "model": self.ai_model,
            },
            "social_tools": self.social_tools,
            "strategy": {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "min_score": self.min_score,
                "sentiment_enabled": self.sentiment_enabled,
            },
            "runtime": {
                "uptime_seconds": round(self.uptime_seconds, 1),
                "webhook_port": self.webhook_port,
                "last_alert_time": self.last_alert_time,
                "alerts_processed": self.alerts_processed,
            },
            "checked_at": self.checked_at,
        }


# ── Singleton status tracker ───────────────────────────────────────
_start_time: float = time.time()
_alerts_count: int = 0
_last_alert: str = ""


def record_alert() -> None:
    """Call this after processing each webhook alert."""
    global _alerts_count, _last_alert  # noqa: PLW0603
    _alerts_count += 1
    _last_alert = datetime.now(timezone.utc).isoformat()


def get_system_status(
    exchange_client: Any = None,
    ai_client: Any = None,
) -> SystemStatus:
    """Collect real-time system health from all components.

    This is a lightweight check — no network calls, just status flags.
    """
    return SystemStatus(
        exchange_connected=exchange_client is not None,
        exchange_id=settings.exchange_id,
        exchange_testnet=settings.exchange_testnet,
        ai_enabled=settings.ai_enabled and ai_client is not None,
        ai_model=settings.anthropic_model if ai_client else "",
        social_tools=get_social_health(),
        symbol=settings.trading_symbol,
        timeframe=settings.timeframe.value,
        min_score=settings.min_signal_score,
        uptime_seconds=time.time() - _start_time,
        webhook_port=settings.webhook_port,
        sentiment_enabled=settings.sentiment_enabled,
        last_alert_time=_last_alert,
        alerts_processed=_alerts_count,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


def get_liveness() -> dict[str, Any]:
    """Quick liveness check — no external calls, just 'am I alive?'"""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "alerts_processed": _alerts_count,
    }


def get_prometheus_metrics(
    exchange_client: Any = None,
    ai_client: Any = None,
) -> str:
    """Generate Prometheus-compatible metrics text.

    Format: https://prometheus.io/docs/concepts/data_model/
    """
    status = get_system_status(exchange_client, ai_client)
    lines: list[str] = []

    # Uptime
    lines.append("# HELP svtr_uptime_seconds Bot uptime in seconds")
    lines.append("# TYPE svtr_uptime_seconds gauge")
    lines.append(f"svtr_uptime_seconds {status.uptime_seconds}")

    # Alerts processed
    lines.append("# HELP svtr_alerts_total Total alerts processed")
    lines.append("# TYPE svtr_alerts_total counter")
    lines.append(f"svtr_alerts_total {status.alerts_processed}")

    # Exchange connected
    lines.append("# HELP svtr_exchange_connected Exchange connection status")
    lines.append("# TYPE svtr_exchange_connected gauge")
    lines.append(f"svtr_exchange_connected {1 if status.exchange_connected else 0}")

    # AI enabled
    lines.append("# HELP svtr_ai_enabled AI layer status")
    lines.append("# TYPE svtr_ai_enabled gauge")
    lines.append(f"svtr_ai_enabled {1 if status.ai_enabled else 0}")

    # Social tools
    lines.append("# HELP svtr_social_tool_available Social CLI tool availability")
    lines.append("# TYPE svtr_social_tool_available gauge")
    for tool, available in status.social_tools.items():
        lines.append(f'svtr_social_tool_available{{tool="{tool}"}} {1 if available else 0}')

    return "\n".join(lines) + "\n"
