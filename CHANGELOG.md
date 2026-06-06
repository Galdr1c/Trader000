# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Multi-symbol scanner (parallel trading across 5-10 pairs)
- Web dashboard (real-time position view, P&L chart)
- Backtesting framework integration (Jesse / freqtrade)
- Backtest↔Live parity test suite
- Walk-forward optimization
- ML-based signal weight optimization
- On-chain metrics integration (Glassnode)

## [1.0.0] — 2025-12-XX

### Phase 4: Production Hardening

#### Added
- Multi-stage Docker build (non-root user, health checks, resource limits)
- Full docker-compose stack: bot + redis + prometheus + grafana
- Prometheus metrics endpoint (`/metrics`)
- Grafana dashboard provisioning
- VPS deployment guide (`docs/DEPLOYMENT.md`)
- TradingView webhook setup guide
- Environment-based configuration (12-factor)
- Decision audit logging with full AI reasoning trail

#### Changed
- `src/main.py` — Refactored to support hybrid MCP Scanner + Webhook modes
- `src/decision/engine.py` — Improved error handling and graceful degradation
- `src/ai_layer/claude_client.py` — Added latency tracking, structured output parsing, retry logic

## [0.4.0] — 2025-12-XX

### Phase 3: AI Layer

#### Added
- `src/ai_layer/claude_client.py` — Async Anthropic SDK wrapper
- `src/ai_layer/trading_agents.py` — TradingAgents (81k⭐) integration
- `src/ai_layer/composite_scorer.py` — Multi-factor decision fusion
- `src/ai_layer/prompts.py` — System prompts for Claude
- `src/ai_layer/decision_logger.py` — Persistent AI decision log
- `tests/test_phase3_ai.py` — AI layer tests
- `tests/test_trading_agents.py` — TradingAgents integration tests

## [0.3.0] — 2025-12-XX

### Phase 2: Data Integration

#### Added
- `src/sentiment/news.py` — RSS + CryptoPanic news aggregator
- `src/sentiment/social.py` — Agent-Reach (Twitter + Reddit) integration
- `src/sentiment/fear_greed.py` — Alternative.me Fear & Greed Index fetcher
- `src/sentiment/market_data.py` — Funding rate + open interest collector
- `src/sentiment/sentiment_pipeline.py` — Composite sentiment orchestrator
- `src/mcp_provider/client.py` — tradingview-mcp client for market data
- `src/scanner/scanner.py` — 24/7 polling scanner
- `tests/test_phase2_data.py` — Sentiment + data tests

## [0.2.0] — 2025-12-XX

### Phase 1: Core Trading Engine

#### Added
- `src/signal_engine/indicators.py` — VWAP, MACD, RSI, ADX, Volume indicators (pandas-ta)
- `src/signal_engine/scoring.py` — 7-factor composite scoring (0–13.5 scale)
- `src/signal_engine/dynamic_tp.py` — Signal-adaptive take profit calculation
- `src/signal_engine/auto_params.py` — Market + timeframe auto-tuning
- `src/decision/engine.py` — Decision orchestration pipeline
- `src/decision/risk.py` — Circuit breaker, position sizing, daily limits
- `src/decision/position.py` — Position state management
- `src/exchange/client.py` — ccxt unified exchange wrapper
- `src/exchange/orders.py` — Order placement + management
- `src/config/settings.py` — Pydantic settings
- `src/monitoring/telegram.py` — Telegram notifier
- `src/monitoring/logger.py` — structlog setup
- `src/monitoring/dashboard.py` — Basic metrics
- `src/monitoring/system.py` — System health checks
- `src/webhook/server.py` — FastAPI webhook server
- `src/webhook/models.py` — TVAlertPayload parser
- `tests/test_signal_engine.py` — Indicator + scoring tests
- `tests/test_decision.py` — Engine + risk tests
- `tests/test_circuit_breaker.py` — Risk limit tests
- `tests/test_e2e_webhook.py` — End-to-end webhook flow

## [0.1.0] — 2025-12-XX

### Initial Release

#### Added
- Smart VWAP Trend Rider v3.8 Pine Script (TradingView)
- Initial Python project structure
- `requirements.txt` and `pyproject.toml`
- `Dockerfile` (basic)
- `.env.example`
- `docs/DEPLOYMENT.md`

[Unreleased]: https://github.com/Galdr1c/Trader000/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Galdr1c/Trader000/releases/tag/v1.0.0
[0.4.0]: https://github.com/Galdr1c/Trader000/releases/tag/v0.4.0
[0.3.0]: https://github.com/Galdr1c/Trader000/releases/tag/v0.3.0
[0.2.0]: https://github.com/Galdr1c/Trader000/releases/tag/v0.2.0
[0.1.0]: https://github.com/Galdr1c/Trader000/releases/tag/v0.1.0
