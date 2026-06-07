"""Tests for TradingAgents integration — multi-agent LLM decision layer."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

# ── Test: TradeRecommendation parsing ──────────────────────────────

def test_trade_recommendation_to_decision_maps_buy() -> None:
    """BUY signal → SVTR decision with approval."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    @dataclass
    class FakeRec:
        signal: str = "BUY"
        confidence: float = 0.85
        size_fraction: float = 0.3
        entry_reference_price: float | None = 65000.0
        target_price: float | None = 72000.0
        stop_loss: float | None = 62000.0
        rationale: str = "Strong bullish momentum"
        warning_message: str | None = None
        currency: str | None = "USD"
        time_horizon_days: int | None = 7

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")
    decision = client._recommendation_to_decision(FakeRec())

    assert decision["approved"] is True
    assert decision["direction"] == "long"
    assert decision["confidence"] == 85
    assert decision["reason"] == "Strong bullish momentum"
    assert decision["tp_adjustment"] == 5.5  # capped at max
    assert decision["risk_level"] == "low"  # confidence=0.85 >= 0.8
    assert decision["entry_price"] == 65000.0
    assert decision["target_price"] == 72000.0
    assert decision["stop_loss"] == 62000.0


def test_trade_recommendation_to_decision_maps_sell() -> None:
    """SELL signal → SVTR decision with short direction."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    @dataclass
    class FakeRec:
        signal: str = "SELL"
        confidence: float = 0.72
        size_fraction: float = 0.2
        entry_reference_price: float | None = 68000.0
        target_price: float | None = 60000.0
        stop_loss: float | None = 71000.0
        rationale: str = "Bearish divergence detected"
        warning_message: str | None = "High volatility"
        currency: str | None = "USD"
        time_horizon_days: int | None = 5

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")
    decision = client._recommendation_to_decision(FakeRec())

    assert decision["approved"] is True
    assert decision["direction"] == "short"
    assert decision["confidence"] == 72
    assert "Bearish divergence detected" in decision["reason"]
    assert "High volatility" in decision["reason"]
    assert decision["warning"] == "High volatility"


def test_trade_recommendation_to_decision_maps_hold() -> None:
    """HOLD signal → SVTR decision rejected."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    @dataclass
    class FakeRec:
        signal: str = "HOLD"
        confidence: float = 0.45
        size_fraction: float = 0.0
        entry_reference_price: float | None = None
        target_price: float | None = None
        stop_loss: float | None = None
        rationale: str = "No clear setup"
        warning_message: str | None = None
        currency: str | None = None
        time_horizon_days: int | None = None

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")
    decision = client._recommendation_to_decision(FakeRec())

    assert decision["approved"] is False
    assert decision["direction"] == "hold"


def test_trade_recommendation_low_confidence_rejected() -> None:
    """Low confidence BUY → rejected (below threshold)."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    @dataclass
    class FakeRec:
        signal: str = "BUY"
        confidence: float = 0.35  # below 0.5 threshold
        size_fraction: float = 0.1
        entry_reference_price: float | None = 65000.0
        target_price: float | None = 68000.0
        stop_loss: float | None = 64000.0
        rationale: str = "Weak signal"
        warning_message: str | None = None
        currency: str | None = "USD"
        time_horizon_days: int | None = 3

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")
    decision = client._recommendation_to_decision(FakeRec())

    assert decision["approved"] is False
    assert "low_confidence" in decision["reason"]


def test_trade_recommendation_error_handling() -> None:
    """TradingAgents exception → graceful fallback decision."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")

    # Simulate an error by passing None
    decision = client._recommendation_to_decision(None)

    assert decision["approved"] is False
    assert decision["action"] == "error"


# ── Test: Confidence scaling ──────────────────────────────────────

def test_confidence_scaling() -> None:
    """Confidence 0-1 → SVTR 0-100 scale."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")

    assert client._scale_confidence(1.0) == 100
    assert client._scale_confidence(0.5) == 50
    assert client._scale_confidence(0.0) == 0
    assert client._scale_confidence(0.85) == 85


# ── Test: Risk level from confidence ──────────────────────────────

def test_risk_level_determination() -> None:
    """Confidence → risk level mapping."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")

    assert client._determine_risk_level(0.9, "BUY") == "low"
    assert client._determine_risk_level(0.7, "BUY") == "medium"
    assert client._determine_risk_level(0.4, "BUY") == "high"
    assert client._determine_risk_level(0.9, "SELL") == "medium"  # SELL always higher risk
    assert client._determine_risk_level(0.5, "SELL") == "high"


# ── Test: TP adjustment from target price ─────────────────────────

def test_tp_adjustment_calculation() -> None:
    """Target price vs entry → TP adjustment %."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")

    # LONG: 65000 → 72000 = 10.76% → capped at 5.5
    adj = client._calculate_tp_adjustment("long", 65000.0, 72000.0)
    assert adj == 5.5

    # LONG: 65000 → 68000 = 4.6%
    adj = client._calculate_tp_adjustment("long", 65000.0, 68000.0)
    assert adj == pytest.approx(4.6, abs=0.1)

    # SHORT: 68000 → 60000 = 11.76% → capped at 5.5
    adj = client._calculate_tp_adjustment("short", 68000.0, 60000.0)
    assert adj == 5.5

    # No target price
    adj = client._calculate_tp_adjustment("long", 65000.0, None)
    assert adj == 0.0


# ── Test: Config builder ──────────────────────────────────────────

def test_build_config() -> None:
    """Config builder creates correct TradingAgentsConfig."""
    pytest.importorskip("tradingagents.config")

    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    client = TradingAgentsDecisionClient(
        anthropic_api_key="test_key",
        deep_think_model="claude-sonnet-4-6",
        quick_think_model="claude-sonnet-4-6",
        max_debate_rounds=2,
    )
    config = client._build_config()

    assert config.llm_provider == "anthropic"
    assert config.deep_think_llm == "claude-sonnet-4-6"
    assert config.quick_think_llm == "claude-sonnet-4-6"
    assert config.max_debate_rounds == 2
    assert config.max_risk_discuss_rounds == 2
    assert config.reasoning_effort == "medium"
    assert config.response_language == "en-US"


# ── Test: Integration format ──────────────────────────────────────

def test_decision_format_matches_engine_expectation() -> None:
    """Decision dict has all keys expected by DecisionEngine."""
    from src.ai_layer.trading_agents import TradingAgentsDecisionClient

    @dataclass
    class FakeRec:
        signal: str = "BUY"
        confidence: float = 0.85
        size_fraction: float = 0.3
        entry_reference_price: float | None = 65000.0
        target_price: float | None = 72000.0
        stop_loss: float | None = 62000.0
        rationale: str = "Bullish"
        warning_message: str | None = None
        currency: str | None = "USD"
        time_horizon_days: int | None = 7

    client = TradingAgentsDecisionClient(anthropic_api_key="test_key")
    decision = client._recommendation_to_decision(FakeRec())

    # Keys expected by DecisionEngine.evaluate_alert()
    expected_keys = {
        "approved", "confidence", "reason", "direction",
        "tp_adjustment", "risk_level", "action",
    }
    assert expected_keys.issubset(set(decision.keys()))
