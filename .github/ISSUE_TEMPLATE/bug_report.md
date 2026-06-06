---
name: 🐛 Bug Report
about: Something isn't working as expected
title: "[BUG] "
labels: ["bug", "needs-triage"]
assignees: []
---

## 🐛 Bug Description

A clear and concise description of what the bug is.

## 📋 Steps to Reproduce

1. Go to '...'
2. Run command '...'
3. Set config '...'
4. See error

## ✅ Expected Behavior

What you expected to happen.

## ❌ Actual Behavior

What actually happened.

## 📸 Screenshots / Logs

If applicable, add screenshots or log output.

```
[paste log output here — REMOVE any API keys, secrets, or account info]
```

## 🌍 Environment

- **OS**: (e.g., Ubuntu 22.04, macOS 14, Windows 11)
- **Python version**: (output of `python --version`)
- **Docker version**: (output of `docker --version`)
- **SVTR Bot version**: (e.g., 1.0.0, or commit hash)
- **Exchange**: (e.g., Binance, Bybit, OKX)
- **Trading pair**: (e.g., BTC/USDT:USDT)
- **Timeframe**: (e.g., 4h, 1h, 15m)

## ⚙️ Configuration

Which environment variables are you using? (omit sensitive values):

```bash
EXCHANGE_ID=
EXCHANGE_TESTNET=
TRADING_SYMBOL=
TIMEFRAME=
MIN_SIGNAL_SCORE=
AI_ENABLED=
SENTIMENT_ENABLED=
```

## 🔍 What I've Tried

What troubleshooting steps have you attempted?

- [ ] Checked the [docs/](docs/) folder
- [ ] Searched [existing issues](https://github.com/Galdr1c/Trader000/issues)
- [ ] Reviewed logs in `docker compose logs svtr-bot`
- [ ] Tried with `EXCHANGE_TESTNET=true`
- [ ] Disabled optional services (AI, sentiment)

## 📌 Additional Context

Add any other context about the problem here.

## ⚠️ Privacy Notice

**Do NOT include** API keys, account numbers, passwords, or any sensitive
information. Issues are public.
