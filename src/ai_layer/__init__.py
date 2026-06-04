"""AI Layer — Claude API integration for signal evaluation and sentiment analysis."""

from src.ai_layer.claude_client import ClaudeClient, AIDecision, SentimentDecision
from src.ai_layer.composite_scorer import CompositeScorer, CompositeScore
from src.ai_layer.decision_logger import AIDecisionLogger

__all__ = [
    "ClaudeClient",
    "AIDecision",
    "SentimentDecision",
    "CompositeScorer",
    "CompositeScore",
    "AIDecisionLogger",
]
