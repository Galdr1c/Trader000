# SVTR Bot — System Architecture

> Comprehensive architectural documentation for the Smart VWAP Trend Rider AI Trading Bot.

---

## 🎯 Design Goals

1. **Faithful reproduction of the SVTR Pine Script** — same signals, same exits, same scoring
2. **Production-grade safety** — multi-layer risk management, circuit breakers, kill switch
3. **AI-augmented decisions** — Claude validates every entry with contextual market data
4. **Observable** — every decision logged, every metric exported, every alert sent
5. **Extensible** — modular design allows swapping AI providers, exchanges, data sources

---

## 📐 Layered Architecture

The system is organized into **6 layers** with clear separation of concerns:

```
┌────────────────────────────────────────────────────────────────────┐
│  Layer 6 — Monitoring & Notifications                             │
│  Telegram, Prometheus, Grafana, structlog, health endpoints       │
├────────────────────────────────────────────────────────────────────┤
│  Layer 5 — Order Management                                        │
│  Exchange client (ccxt), order placement, TP/SL tracking          │
├────────────────────────────────────────────────────────────────────┤
│  Layer 4 — Decision Engine                                         │
│  Multi-factor decision pipeline (risk → signal → AI → execution)  │
├────────────────────────────────────────────────────────────────────┤
│  Layer 3 — AI Intelligence                                         │
│  Claude API, TradingAgents, Composite Scorer, Decision Logger     │
├────────────────────────────────────────────────────────────────────┤
│  Layer 2 — Signal Engine + Sentiment                               │
│  Indicator calc, scoring, dynamic TP, news/social/fear-greed      │
├────────────────────────────────────────────────────────────────────┤
│  Layer 1 — Data Ingestion                                          │
│  MCP Scanner, TradingView webhook, exchange WebSocket, RSS feeds  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow — Full Trade Lifecycle

### Entry Path

```
[Bar Closes / Alert Triggered]
        │
        ▼
┌──────────────────┐
│ Layer 1:         │
│  Data Ingestion  │ ← MCP Scanner polls every N seconds
│                  │ ← Webhook receives TV alert
│                  │ ← Sentiment data fetched in parallel
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Layer 2:         │
│  Signal Engine   │ ← Calculate VWAP, MACD, RSI, ADX
│                  │ ← Compute 7-factor score (0-13.5)
│                  │ ← If score >= 8.0, proceed
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Layer 4:         │
│  Decision Engine │ ← Step 1: Risk check (can_trade?)
│                  │ ← Step 2: Signal quality (score threshold)
│                  │ ← Step 3: Fetch market context
│                  │ ← Step 4: AI evaluation (Claude)
│                  │ ← Step 5: Position sizing
│                  │ ← Step 6: Calculate TP/SL
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Layer 5:         │
│  Order Mgmt      │ ← Place market order
│                  │ ← Set TP/SL exchange-side (OCO)
│                  │ ← Store position state in Redis
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Layer 6:         │
│  Monitoring      │ ← Send Telegram alert
│                  │ ← Increment Prometheus counter
│                  │ ← Log full AI decision trail
└──────────────────┘
```

### Exit Path

```
[Position Open in Exchange]
        │
        ▼
[Each New Bar / Tick]
        │
        ├─→ Check Max Loss
        ├─→ Check Stop Loss (ATR)
        ├─→ Check Trailing Stop
        ├─→ Check TP Levels (chunked)
        ├─→ Check Pullback Bulk TP
        ├─→ Check VWAP Exit
        ├─→ Check Signal Degradation
        ├─→ Check Time Decay
        └─→ Check Auto-Close
        │
        ▼
[If exit triggered]
        │
        ▼
┌──────────────────┐
│ Layer 5:         │
│  Order Mgmt      │ ← Place close order
│                  │ ← Update position state
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Layer 6:         │
│  Monitoring      │ ← Update trade stats table
│                  │ ← Send Telegram exit alert
│                  │ ← Risk manager: record result
└──────────────────┘
```

---

## 🧩 Module Reference

### `src/main.py` — Application Entry Point

**Responsibility:** Application bootstrap, dependency injection, lifecycle management.

- Creates FastAPI app with lifespan context
- Initializes all singletons (risk manager, position manager, exchange, AI, scanner)
- Starts MCP scanner as background task
- Handles graceful shutdown

**Key functions:**
- `lifespan()` — async context manager for startup/shutdown
- `main()` — runs uvicorn server

### `src/signal_engine/` — Technical Analysis

| File | Purpose |
|------|---------|
| `indicators.py` | VWAP, MACD, RSI, ADX, ATR, Volume, ROC calculations (pandas-ta) |
| `scoring.py` | 7-factor composite scoring with weighted aggregation |
| `dynamic_tp.py` | TP distance calculation based on signal + trend + momentum |
| `auto_params.py` | Auto-adaptation by market type and timeframe |

**Key insight:** `scoring.py` is a **1:1 reimplementation** of the Pine Script's `f_calculateSignalStrength` function. Score range: 0.0 (no signal) to 13.5 (perfect storm).

### `src/decision/` — Decision Logic

| File | Purpose |
|------|---------|
| `engine.py` | Orchestrates the full pipeline: alert → market → AI → order |
| `risk.py` | Circuit breaker, daily P&L tracking, cooldown enforcement |
| `position.py` | Position state, TP chunking logic, exit type tracking |

**Critical invariant:** Every entry passes through `RiskManager.can_trade()` first. If the circuit breaker is active, no trade is placed regardless of signal quality.

### `src/ai_layer/` — AI Integration

| File | Purpose |
|------|---------|
| `claude_client.py` | Async Anthropic SDK wrapper with retry, latency tracking, JSON parsing |
| `trading_agents.py` | Wraps TauricResearch/TradingAgents (81k⭐) multi-agent framework |
| `composite_scorer.py` | Fuses technical + sentiment + AI scores |
| `prompts.py` | System prompts and task-specific templates |
| `decision_logger.py` | Persists AI decisions for post-hoc analysis |

**Two AI strategies, used in parallel:**

1. **Direct Claude** — Quick yes/no with TP adjustment (~500ms latency)
2. **TradingAgents** — Full multi-agent debate (~5-15s, higher quality)

### `src/sentiment/` — Market Intelligence

| File | Purpose |
|------|---------|
| `sentiment_pipeline.py` | Orchestrates all sentiment sources, produces -1.0 to +1.0 score |
| `news.py` | RSS + CryptoPanic news aggregation with coin filtering |
| `social.py` | Twitter/X + Reddit via Agent-Reach CLI tools |
| `fear_greed.py` | Alternative.me Fear & Greed Index |
| `market_data.py` | Funding rate, open interest, 24h volume change |

**Graceful degradation:** Each source is independent. If Agent-Reach CLIs are missing, the bot still runs with reduced sentiment (only RSS + Fear & Greed).

### `src/exchange/` — Exchange Connectivity

| File | Purpose |
|------|---------|
| `client.py` | ccxt-based async wrapper for 100+ exchanges |
| `orders.py` | Order placement, TP/SL management, position queries |

### `src/monitoring/` — Observability

| File | Purpose |
|------|---------|
| `telegram.py` | Async Telegram bot for alerts + kill switch |
| `logger.py` | structlog setup with JSON output |
| `dashboard.py` | Prometheus metric definitions |
| `system.py` | System health checks (disk, memory, CPU) |

### `src/webhook/` — Webhook Mode

| File | Purpose |
|------|---------|
| `server.py` | FastAPI server with HMAC verification |
| `models.py` | TVAlertPayload parser for TradingView alert format |
| `tradingview_setup.md` | User-facing setup guide for TradingView alerts |

### `src/scanner/` — Polling Mode

| File | Purpose |
|------|---------|
| `scanner.py` | 24/7 polling loop via tradingview-mcp |

**Two operating modes:**

1. **MCP Scanner (default)** — Bot polls market data every N seconds. No external dependencies (no TradingView account, no webhook URL, no ngrok).
2. **Webhook** — TradingView sends alerts via HTTP POST. Lower latency, requires public HTTPS URL.

---

## 🔐 Security Model

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: API Key Isolation                                 │
│  • Read-only keys for market data                           │
│  • Trade keys have NO withdrawal permission                 │
│  • IP whitelist on exchange side                            │
│  • Testnet by default                                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Runtime Safety                                    │
│  • Non-root Docker user                                     │
│  • Read-only filesystem (where possible)                    │
│  • No outbound network except to whitelisted APIs           │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Risk Limits                                       │
│  • Daily max loss → full stop                               │
│  • Consecutive stop counter → cooldown                      │
│  • Per-trade position size cap                              │
│  • Max drawdown → manual intervention                       │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: AI Override                                       │
│  • Claude "approved: false" → trade rejected                │
│  • High risk_level → position size halved                   │
│  • Critical news → 60-min pause                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Manual Kill Switch                                │
│  • `/stop` Telegram command                                 │
│  • Emergency close all positions                            │
│  • Pause scanner without restart                            │
└─────────────────────────────────────────────────────────────┘
```

### Secret Management

- `.env` file is **never committed** (`.gitignore` enforced)
- Production deployment should use:
  - Docker secrets, OR
  - HashiCorp Vault, OR
  - AWS Secrets Manager / GCP Secret Manager
- HMAC verification on webhooks prevents unauthorized orders

---

## 📊 Data Storage

| Data | Storage | Retention | Purpose |
|------|---------|-----------|---------|
| Position state | Redis | Live (TTL 7d) | Fast access during trades |
| Trade history | Local JSON files | Forever | Backtesting, audit |
| AI decisions | Local JSON files | Forever | Post-hoc analysis |
| Prometheus metrics | Prometheus TSDB | 30 days | Grafana dashboards |
| Logs | Docker volumes / log files | 30 days (rotate) | Debugging |
| Sentiment snapshots | Redis | 1 hour (TTL) | Cache layer |

---

## 🌐 External Dependencies

| Service | Required | Purpose | Fallback |
|---------|:--------:|---------|----------|
| Exchange (Binance) | ✅ | Trade execution | None (bot cannot run) |
| Anthropic Claude | ⚠️ Optional | AI evaluation | Bot runs without AI |
| TradingAgents | ⚠️ Optional | Multi-agent debate | Direct Claude instead |
| Telegram | ⚠️ Optional | Notifications | Logs only |
| RSS feeds | ❌ Optional | News sentiment | Sentiment score = 0 |
| Twitter / Reddit (Agent-Reach) | ❌ Optional | Social sentiment | Sentiment score = 0 |
| Prometheus / Grafana | ❌ Optional | Metrics | Logs only |

**The bot is designed to run with degraded functionality if optional services are unavailable.**

---

## 🔄 State Machine — Position Lifecycle

```
   ┌──────────┐
   │  FLAT    │  (no position)
   └────┬─────┘
        │ signal approved, order filled
        ▼
   ┌──────────┐
   │  OPEN    │  (position active)
   └────┬─────┘
        │ exit signal triggered
        ├─→ TP1 (partial close) ─→ still OPEN, chunks++
        ├─→ TP2 (partial close) ─→ still OPEN, chunks++
        ├─→ TP3+ or Bulk TP ─→ may fully close
        ├─→ Trailing Stop ─→ CLOSED
        ├─→ Max Loss ─→ CLOSED
        ├─→ VWAP Exit ─→ CLOSED
        ├─→ Signal Drop ─→ CLOSED
        └─→ Time Decay ─→ CLOSED
        ▼
   ┌──────────┐
   │  FLAT    │  (position closed, ready for next signal)
   └──────────┘
```

Each transition is logged with:
- Timestamp
- Exit reason (from `ExitType` enum)
- P&L percentage
- Position size at exit
- AI confidence at entry (for attribution)

---

## 🚀 Deployment Topology

### Single-VPS Production (recommended)

```
┌─────────────────────────────────────────────────────┐
│  VPS (Ubuntu 22.04+, 2 vCPU, 2 GB RAM)             │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Docker Compose Stack                        │  │
│  │                                              │  │
│  │  [svtr-bot:8000]  [redis:6379]               │  │
│  │  [prometheus:9090]  [grafana:3000]           │  │
│  │                                              │  │
│  │  All on internal svtr-net bridge             │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  Persistent volumes:                                │
│  - redis-data, prometheus-data, grafana-data        │
│  - ./data (trade history, AI decisions)             │
│  - ./logs (structured logs)                         │
└─────────────────────────────────────────────────────┘
            │                           │
            ▼                           ▼
   [Binance API]            [Anthropic API]
   [Telegram API]           [External RSS feeds]
```

### High-Availability (optional, future)

- Two VPS instances, primary + hot standby
- Shared Redis (managed) for state
- DNS failover with health checks
- Telegram alerts on VPS failure

---

## 📈 Performance Characteristics

| Metric | Typical Value |
|--------|---------------|
| MCP Scanner latency | 200–800ms per scan |
| Claude API call | 500–2000ms |
| TradingAgents analysis | 5–15 seconds |
| Decision-to-order latency | 100–300ms |
| Memory footprint | ~150–250 MB |
| CPU usage (idle) | <5% |
| CPU usage (active trade) | 10–20% |
| Daily API calls (Claude) | 50–200 |
| Daily API calls (exchange) | 200–500 |

---

## 🔮 Future Evolution

See [ROADMAP.md](ROADMAP.md) (planned) and [CHANGELOG.md](../CHANGELOG.md) for completed work.

**Architectural evolution path:**

1. **v1.0 (current)** — Single bot, single symbol, MCP scanner
2. **v1.5** — Multi-symbol scanner, portfolio-level risk
3. **v2.0** — Multi-strategy engine (add mean-reversion, breakout strategies)
4. **v3.0** — Distributed backtesting + parameter optimization (Ray cluster)
5. **v4.0** — On-prem LLM (replace Claude with local fine-tuned model)

---

<p align="center">
  <sub>For questions about architecture, open a GitHub Discussion.</sub>
</p>
