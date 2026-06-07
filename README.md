# 🤖 SVTR Bot — Smart VWAP Trend Rider AI Trading Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests](https://img.shields.io/badge/tests-pytest-blueviolet.svg)](https://docs.pytest.org/)
[![GitHub stars](https://img.shields.io/github/stars/Galdr1c/Trader000.svg)](https://github.com/Galdr1c/Trader000/stargazers)

> **AI-powered 24/7 crypto trading bot built on top of the [Smart VWAP Trend Rider (SVTR) v3.8](https://www.tradingview.com/) Pine Script strategy.**

SVTR Bot brings a sophisticated multi-indicator Pine Script strategy into a production-grade Python trading system, enhanced with **Claude AI** for contextual decision-making, **TradingAgents** multi-agent LLM framework, real-time **sentiment analysis** (news + social + on-chain), and a complete **risk management** layer with circuit breakers.

---

## ✨ Features

### 📊 Trading Engine
- **1:1 Pine Script reimplementation** — VWAP + MACD + RSI + ADX + Volume scoring (0–13.5 weighted scale)
- **Dynamic TP system** — Take profit distance adapts to signal strength, ADX trend, and momentum
- **7 exit mechanisms** — TP chunks, trailing stop, VWAP exit, signal degradation, time decay, max loss, auto-close
- **Multi-timeframe adaptive** — Auto-tunes parameters for crypto, forex, stocks across 1m → monthly

### 🧠 AI Layer
- **Claude API integration** (Anthropic SDK) — Real-time contextual trade evaluation
- **TradingAgents framework** (81k⭐) — Multi-agent LLM debate: technical, sentiment, news, fundamental, risk managers
- **Composite scoring** — Combines technical signal + AI evaluation + market context
- **Decision logging** — Full audit trail of every AI decision with latency tracking

### 🌍 Sentiment & Market Intelligence
- **News aggregation** — RSS feeds (CoinTelegraph, Decrypt, The Block) + CryptoPanic API
- **Social media** — Twitter/X + Reddit via [Agent-Reach](https://github.com/Panniantong/Agent-Reach) (free, cookie-based)
- **Fear & Greed Index** — Real-time market sentiment indicator
- **Market data** — Funding rates, open interest, liquidations (via tradingview-mcp)

### 🛡️ Risk Management
- **Circuit breaker** — Auto-shutdown on daily max loss (default 5%)
- **Consecutive stop limit** — Pause after N consecutive stops (default 3)
- **Cooldown periods** — Enforced between trades and after stop sequences
- **Position sizing** — Adaptive based on signal score and AI risk assessment
- **TP chunking** — Scale out positions to lock profits progressively

### 🏗️ Production Infrastructure
- **Two operating modes**:
  - **MCP Scanner** (default) — 24/7 polling via tradingview-mcp, no webhooks needed
  - **Webhook Server** — Receives TradingView alerts via HTTP POST
- **Multi-stage Docker** — Non-root user, health checks, resource limits
- **Full monitoring stack** — Prometheus metrics + Grafana dashboards
- **Telegram notifications** — Real-time trade alerts, status updates, kill switch
- **Redis state** — Fast in-memory state cache
- **FastAPI webhook** — Async, type-hinted, OpenAPI-documented

---

## 🏛️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    SVTR Bot — System Architecture                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  MCP Scanner │  │TradingView   │  │  Exchange    │                │
│  │  (24/7 poll) │  │  Webhook     │  │  WebSocket   │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                │
│         │                 │                  │                       │
│         └─────────────────┼──────────────────┘                       │
│                           ▼                                         │
│              ┌──────────────────────────┐                           │
│              │   Decision Engine        │                           │
│              │  ┌────────────────────┐  │                           │
│              │  │ 1. Risk Check      │  │                           │
│              │  │ 2. Signal Quality  │  │                           │
│              │  │ 3. Market Context  │  │                           │
│              │  │ 4. AI Evaluation   │  │                           │
│              │  │ 5. Position Sizing │  │                           │
│              │  │ 6. TP/SL Calc      │  │                           │
│              │  │ 7. Order Execute   │  │                           │
│              │  └────────────────────┘  │                           │
│              └────────────┬─────────────┘                           │
│                           │                                         │
│         ┌─────────────────┼─────────────────┐                       │
│         ▼                 ▼                 ▼                       │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ Signal      │  │  Sentiment   │  │   AI Layer   │                │
│  │ Engine      │  │  Pipeline    │  │              │                │
│  │ (Python)    │  │ • News       │  │ • Claude API │                │
│  │ • VWAP      │  │ • Twitter    │  │ • Trading    │                │
│  │ • MACD      │  │ • Reddit     │  │   Agents     │                │
│  │ • RSI       │  │ • Fear&Greed │  │ • Composite  │                │
│  │ • ADX       │  │ • Funding    │  │   Scorer     │                │
│  │ • Scoring   │  │              │  │              │                │
│  └─────────────┘  └──────────────┘  └──────────────┘                │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │  Monitoring: Prometheus + Grafana + Telegram + Logs      │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

📐 **[Full architecture documentation →](docs/ARCHITECTURE.md)**

---

## 🚀 Quick Start

### Prerequisites

- **Docker** 24.0+ and **Docker Compose** v2.20+
- **Binance** (or Bybit / OKX / Kraken) account with API keys
- **Anthropic Claude** API key
- **Telegram** bot token (optional, for notifications)

### 1. Clone & Configure

```bash
git clone https://github.com/Galdr1c/Trader000.git
cd Trader000
cp .env.example .env
nano .env  # Fill in your API keys
```

### 2. Launch

```bash
docker compose up -d
```

This starts the full stack:

| Service | Port | Purpose |
|---------|------|---------|
| `svtr-bot` | 8000 | Trading bot (FastAPI) |
| `redis` | 6379 | State cache & pub/sub |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3000 | Dashboards (admin / svtr-bot-2024) |

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health

# View logs
docker compose logs -f svtr-bot

# Open Grafana
open http://localhost:3000
```

### 4. Stop

```bash
docker compose down
```

📖 **[Detailed VPS deployment guide →](docs/DEPLOYMENT.md)**

---

## ⚙️ Configuration

All configuration via environment variables (see [`.env.example`](.env.example)):

| Variable | Description | Default |
|----------|-------------|---------|
| `EXCHANGE_ID` | Exchange to trade on (binance, bybit, okx) | `binance` |
| `EXCHANGE_TESTNET` | Use testnet (always `true` for first run) | `true` |
| `TRADING_SYMBOL` | Pair to trade | `BTC/USDT:USDT` |
| `TRADING_SYMBOLS` | Comma-separated pairs for parallel scanning | falls back to `TRADING_SYMBOL` |
| `MAX_CONCURRENT_SCANS` | Maximum simultaneous market scans | `3` |
| `MAX_ACTIVE_POSITIONS` | Portfolio position-count limit | `3` |
| `MAX_PORTFOLIO_EXPOSURE_PCT` | Maximum aggregate nominal exposure | `80` |
| `TIMEFRAME` | Strategy timeframe | `4h` |
| `MIN_SIGNAL_SCORE` | Minimum composite score to enter (0–13.5) | `8.0` |
| `POSITION_SIZE_PCT` | Position size as % of equity | `20` |
| `DAILY_MAX_LOSS_PCT` | Circuit breaker threshold | `5.0` |
| `CONSECUTIVE_STOP_LIMIT` | Cooldown trigger | `3` |
| `COOLDOWN_HOURS` | Cooldown duration | `24` |
| `SCAN_INTERVAL_SECONDS` | MCP scanner poll interval | `60` |
| `SENTIMENT_ENABLED` | Enable sentiment pipeline | `true` |
| `AI_ENABLED` | Enable Claude AI evaluation | `true` |
| `ANTHROPIC_API_KEY` | Claude API key | required |
| `ANTHROPIC_MODEL` | Claude model | `claude-sonnet-4-20250514` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | optional |
| `TELEGRAM_CHAT_ID` | Chat ID for notifications | optional |

---

## 🎯 Strategy: Smart VWAP Trend Rider v3.8

This bot implements the **SVTR Ultimate v3.8** TradingView Pine Script with the following architecture:

### Signal Scoring (0–13.5 scale)

| Component | Max Weight | Description |
|-----------|-----------:|-------------|
| **VWAP Breakout** | 2.5 | Price position relative to smoothed VWAP + breakout strength |
| **MACD** | 2.5 | MACD line vs signal + histogram acceleration |
| **Volume** | 2.0 | Volume vs 20-bar SMA |
| **ADX** | 2.0 | Trend strength + DI+/DI- alignment + momentum bonus |
| **Trend Filter** | 1.5 | 200 EMA direction & strength |
| **Momentum** | 1.0 | Rate of change |
| **RSI** | 1.0 | RSI vs threshold + 3-bar consistency |

**Entry requires `score >= MIN_SIGNAL_SCORE`** (default 8.0).

### Exit Mechanisms (7 types)

1. **TP Chunking** — Close `chunkPct` (10–12.5%) at each TP level
2. **Pullback Bulk TP** — Close multiple TP levels if price retraces `pullbackPct`
3. **Trailing Stop** — Activates after `trailingActivationPct` profit
4. **VWAP Exit** — Close if price crosses back through VWAP for N bars
5. **Signal Degradation** — Close if live score drops by X% of entry score
6. **Time Decay** — Close if no TP hit within N bars
7. **Max Loss** — Hard stop at `maxLossPct`
8. **Auto-Close** — Close remaining position if < `autoCloseThreshold`%

### Auto-Adaptation

The strategy **auto-tunes** parameters based on:

- **Market type** — Crypto / Forex / Stocks (detected from symbol prefix)
- **Timeframe** — 1m to Monthly (5 buckets)
- **Volatility** — ATR-based stop multiplier scales with timeframe

---

## 🛡️ Risk Warnings

> ⚠️ **This bot trades real money. Algorithmic trading involves significant risk.**

- ✅ Always start with `EXCHANGE_TESTNET=true`
- ✅ Minimum **3 months** of paper trading before live
- ✅ Start with **small position sizes** (1–5% equity)
- ✅ **Never** trade with money you can't afford to lose
- ✅ Backtest results ≠ live performance (slippage, latency, partial fills)
- ✅ Past performance does not guarantee future results

**The maintainers are not responsible for financial losses incurred by using this software.**

---

## 🗺️ Roadmap

### ✅ Phase 1–4 (Completed)
- [x] Pine Script reimplementation in Python
- [x] ccxt exchange integration
- [x] Risk management with circuit breaker
- [x] Claude API + TradingAgents integration
- [x] Sentiment pipeline (news + social + Fear & Greed)
- [x] Multi-stage Docker deployment
- [x] Prometheus + Grafana monitoring
- [x] Telegram notifications

### ✅ Phase 5 (Completed)
- [x] Multi-symbol scanner (bounded parallel trading)
- [x] Web dashboard (real-time positions and P&L)
- [x] Jesse backtesting framework integration
- [x] Backtest↔Live parity tests
- [x] CI with GitHub Actions
- [x] Walk-forward optimization

See [Jesse backtesting and walk-forward usage](docs/BACKTESTING.md).

### 🔮 Phase 6 (Planned)
- [ ] ML-based signal weight optimization
- [ ] Portfolio-level risk management
- [ ] On-chain metrics integration (Glassnode)
- [ ] Multi-exchange arbitrage module
- [ ] WebSocket-based real-time execution
- [ ] Voice alerts via Telegram

See [CHANGELOG.md](CHANGELOG.md) for detailed history.

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built on top of these amazing open-source projects:

- **[TradingView](https://www.tradingview.com/)** — SVTR v3.8 Pine Script strategy by Mo1ra
- **[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)** (81k⭐) — Multi-agent LLM framework
- **[Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach)** (20.3k⭐) — Social media CLI tools
- **[ccxt/ccxt](https://github.com/ccxt/ccxt)** (35k⭐) — Unified exchange API
- **[Anthropic Claude](https://www.anthropic.com/)** — AI backbone
- **[freqtrade](https://github.com/freqtrade/freqtrade)** (45.9k⭐) — Reference bot architecture
- **[FastAPI](https://fastapi.tiangolo.com/)** — Web framework
- **[Prometheus](https://prometheus.io/) + [Grafana](https://grafana.com/)** — Monitoring stack

---

## 📬 Contact

- **GitHub Issues**: [github.com/Galdr1c/Trader000/issues](https://github.com/Galdr1c/Trader000/issues)
- **Original strategy**: [Smart VWAP Trend Rider Ultimate v3.8](https://www.tradingview.com/)

---

<p align="center">
  <sub>If this project helped you, consider giving it a ⭐!</sub>
</p>
