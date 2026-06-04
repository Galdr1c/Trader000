"""AI Decision Logger — records every AI evaluation for analysis.

Stores decisions in a local JSONL file for:
- Accuracy tracking (AI approved/rejected → actual outcome)
- Prompt optimization (A/B testing different prompts)
- Performance monitoring (latency, confidence distribution)
- Audit trail (regulatory compliance)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)

# Decision log file path
_DECISION_LOG = settings.data_dir / "ai_decisions.jsonl"


@dataclass
class AIDecisionRecord:
    """Single AI decision record for logging."""

    timestamp: str = ""
    event_type: str = ""  # "signal_eval" | "sentiment" | "trade_outcome"

    # Signal evaluation fields
    symbol: str = ""
    direction: str = ""
    signal_score: float = 0.0
    approved: bool = False
    ai_confidence: int = 0
    ai_risk_level: str = ""
    ai_reason: str = ""
    tp_adjustment: float = 0.0

    # Market context snapshot
    funding_rate: float = 0.0
    fear_greed: int = 50
    volume_ratio: float = 1.0
    sentiment_score: float = 0.0

    # Performance tracking
    latency_ms: float = 0.0
    model: str = ""
    composite_score: float = 0.0
    composite_decision: str = ""

    # Trade outcome (filled in later)
    outcome_pnl: float | None = None
    outcome_exit_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v is not None}


class AIDecisionLogger:
    """Logs AI decisions to JSONL file for post-trade analysis."""

    def __init__(self, log_path: Path | None = None) -> None:
        self._log_path = log_path or _DECISION_LOG
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_signal_eval(
        self,
        symbol: str,
        direction: str,
        signal_score: float,
        approved: bool,
        ai_confidence: int,
        ai_risk_level: str,
        ai_reason: str,
        tp_adjustment: float,
        funding_rate: float,
        fear_greed: int,
        volume_ratio: float,
        sentiment_score: float,
        latency_ms: float,
        model: str,
        composite_score: float = 0.0,
        composite_decision: str = "",
    ) -> None:
        """Log a signal evaluation decision."""
        record = AIDecisionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="signal_eval",
            symbol=symbol,
            direction=direction,
            signal_score=signal_score,
            approved=approved,
            ai_confidence=ai_confidence,
            ai_risk_level=ai_risk_level,
            ai_reason=ai_reason,
            tp_adjustment=tp_adjustment,
            funding_rate=funding_rate,
            fear_greed=fear_greed,
            volume_ratio=volume_ratio,
            sentiment_score=sentiment_score,
            latency_ms=latency_ms,
            model=model,
            composite_score=composite_score,
            composite_decision=composite_decision,
        )
        self._write(record)

    def log_trade_outcome(
        self,
        symbol: str,
        direction: str,
        signal_score: float,
        pnl_pct: float,
        exit_type: str,
        ai_confidence: int = 0,
        ai_reason: str = "",
        model: str = "",
    ) -> None:
        """Log trade outcome for accuracy tracking."""
        record = AIDecisionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="trade_outcome",
            symbol=symbol,
            direction=direction,
            signal_score=signal_score,
            outcome_pnl=pnl_pct,
            outcome_exit_type=exit_type,
            ai_confidence=ai_confidence,
            ai_reason=ai_reason,
            model=model,
        )
        self._write(record)

    def get_stats(self, last_n: int = 100) -> dict[str, Any]:
        """Get accuracy statistics from decision log.

        Returns accuracy metrics for AI-approved vs rejected trades.
        """
        records = self._read_recent(last_n)

        approved_trades = [r for r in records if r.get("event_type") == "trade_outcome"]
        signal_evals = [r for r in records if r.get("event_type") == "signal_eval"]

        # Approval rate
        total_evals = len(signal_evals)
        approved = sum(1 for r in signal_evals if r.get("approved"))
        approval_rate = approved / total_evals if total_evals > 0 else 0.0

        # Win rate for approved trades
        wins = sum(1 for r in approved_trades if (r.get("outcome_pnl") or 0) > 0)
        win_rate = wins / len(approved_trades) if approved_trades else 0.0

        # Average latency
        latencies = [r.get("latency_ms", 0) for r in signal_evals if r.get("latency_ms")]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        return {
            "total_evaluations": total_evals,
            "approval_rate": round(approval_rate, 3),
            "total_outcomes": len(approved_trades),
            "win_rate": round(win_rate, 3),
            "avg_latency_ms": round(avg_latency, 1),
        }

    def _write(self, record: AIDecisionRecord) -> None:
        """Append a record to the JSONL log file."""
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("decision_log_write_error | %s", e)

    def _read_recent(self, n: int = 100) -> list[dict]:
        """Read the last N records from the log file."""
        try:
            if not self._log_path.exists():
                return []
            lines = self._log_path.read_text(encoding="utf-8").strip().split("\n")
            return [json.loads(line) for line in lines[-n:] if line.strip()]
        except Exception as e:
            logger.warning("decision_log_read_error | %s", e)
            return []
