"""AI Layer — Claude API + TradingAgents integration for signal evaluation."""

from src.ai_layer.claude_client import AIDecision, ClaudeClient, SentimentDecision
from src.ai_layer.composite_scorer import CompositeScore, CompositeScorer
from src.ai_layer.decision_logger import AIDecisionLogger
from src.ai_layer.trading_agents import TradingAgentsDecisionClient

__all__ = [
    "ClaudeClient",
    "AIDecision",
    "SentimentDecision",
    "CompositeScorer",
    "CompositeScore",
    "AIDecisionLogger",
    "TradingAgentsDecisionClient",
]
