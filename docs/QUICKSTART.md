# Quick Start Guide

> Get SVTR Bot running in **5 minutes** with this step-by-step walkthrough.

This guide assumes you're running on a Linux/macOS system with Docker installed. For full VPS deployment, see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## 1️⃣ Prerequisites (1 minute)

Install if you don't have them:

- **Docker** & **Docker Compose**: https://docs.docker.com/get-docker/
- **Git**: https://git-scm.com/downloads

Verify:

```bash
docker --version        # 24.0+
docker compose version  # v2.20+
git --version
```

---

## 2️⃣ Clone the Repository (30 seconds)

```bash
git clone https://github.com/Galdr1c/Trader000.git
cd Trader000
```

---

## 3️⃣ Configure Environment (1 minute)

```bash
cp .env.example .env
```

Edit `.env` with your favorite editor:

```bash
nano .env
```

**Minimum required variables:**

```bash
# Exchange — start with testnet ALWAYS
EXCHANGE_ID=binance
EXCHANGE_API_KEY=your_binance_testnet_api_key
EXCHANGE_SECRET=your_binance_testnet_secret
EXCHANGE_TESTNET=true

# AI — required for full functionality
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**How to get testnet API keys:**

1. Go to https://testnet.binancefuture.com/
2. Log in with GitHub
3. Click "API Key" at bottom of page
4. Copy the key and secret

**How to get Anthropic API key:**

1. Go to https://console.anthropic.com/
2. Create account, add credits
3. Generate API key under "Settings"

**Optional — Telegram notifications:**

```bash
# Create a bot via @BotFather on Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-100123456789
```

---

## 4️⃣ Start the Stack (1 minute)

```bash
docker compose up -d
```

Wait ~30 seconds for all services to initialize. Check status:

```bash
docker compose ps
```

You should see:

```
NAME                STATUS              PORTS
svtr-bot            Up (healthy)        0.0.0.0:8000->8000/tcp
svtr-redis          Up (healthy)        0.0.0.0:6379->6379/tcp
svtr-prometheus     Up                  0.0.0.0:9090->9090/tcp
svtr-grafana        Up                  0.0.0.0:3000->3000/tcp
```

---

## 5️⃣ Verify It's Working (1 minute)

```bash
# Health check
curl http://localhost:8000/health

# Should return:
# {"status":"ok","version":"1.0.0","mode":"mcp_scanner"}
```

**View live logs:**

```bash
docker compose logs -f svtr-bot
```

You should see startup messages:

```
svtr_bot_starting | version=1.0.0
mcp_client_initialized
exchange_connected | binance (testnet)
ai_client_initialized | model=claude-sonnet-4-20250514
trading_agents_initialized | model=claude-sonnet-4-20250514
scanner_started | interval=60s | symbols=['BTC']
svtr_bot_ready | exchange=binance | ai=on | mcp=on | symbol=BTC/USDT:USDT
```

**Open Grafana dashboard:**

```
http://localhost:3000
Login: admin / svtr-bot-2024
```

You should see the "SVTR Bot — Trading Overview" dashboard auto-loaded.

---

## 6️⃣ Watch It Trade (ongoing)

The bot will:

1. **Every 60 seconds** — scan BTC/USDT 4h candles for signals
2. **When signal score >= 8.0** — evaluate with Claude AI
3. **If approved** — place testnet order with TP/SL
4. **Continuously** — monitor position, adjust exits, log to Grafana

**Telegram notifications** will arrive for:
- Bot start/stop
- Trade entries (with AI reasoning)
- TP hits
- Stop losses
- Circuit breaker triggers
- Daily P&L summary

---

## 🆘 Troubleshooting

### Bot won't start

```bash
# Check detailed logs
docker compose logs svtr-bot

# Common issues:
# 1. API key invalid → check .env
# 2. Exchange not reachable → check firewall, try testnet
# 3. Anthropic key invalid → check console.anthropic.com
```

### No trades happening

This is **normal** at first — SVTR is selective. Possible reasons:

1. **Min score too high** — try `MIN_SIGNAL_SCORE=7.0` temporarily
2. **No signals in current market** — try a more volatile pair (ETH/USDT)
3. **Bot just started** — wait 1-2 hours for first scan
4. **Risk limits active** — check Telegram for circuit breaker alerts

### Grafana dashboard empty

```bash
# Verify Prometheus is scraping
curl http://localhost:9090/targets

# Should show "svtr-bot" target as "up"
```

### High memory usage

```bash
# Check current usage
docker stats svtr-bot

# If over 400MB, restart
docker compose restart svtr-bot
```

---

## 🛑 Stop the Stack

```bash
# Graceful shutdown
docker compose down

# Or via Telegram (if configured)
/stop
```

---

## 🔄 Update to Latest Version

```bash
git pull
docker compose pull
docker compose up -d --build
```

---

## 🎓 Next Steps

Once your bot is running smoothly on testnet for 1-2 weeks:

1. **Review logs** — understand the decision flow
2. **Tune parameters** — adjust `MIN_SIGNAL_SCORE`, `POSITION_SIZE_PCT`
3. **Add more symbols** — see [Multi-Symbol Setup Guide](MULTI_SYMBOL.md) (TBD)
4. **Walk-forward optimize** — see [Optimization Guide](OPTIMIZATION.md) (TBD)
5. **Go live (carefully)** — see [Live Trading Checklist](LIVE_TRADING.md) (TBD)

---

<p align="center">
  <sub>Happy trading! 🚀</sub>
</p>
