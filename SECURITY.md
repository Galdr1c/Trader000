# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| 0.4.x   | :white_check_mark: |
| < 0.4   | :x:                |

## Reporting a Vulnerability

The SVTR Bot team takes security bugs seriously. We appreciate your efforts to responsibly disclose your findings.

### How to Report

**Please DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of these methods:

1. **GitHub Security Advisories** (preferred):
   Navigate to https://github.com/Galdr1c/Trader000/security/advisories/new
   and submit a private security advisory.

2. **Email**: Send to the repository owner via GitHub profile
   (https://github.com/Galdr1c) — use the subject line `SECURITY: SVTR Bot`.

### What to Include

Please include the following information in your report:

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, command injection, etc.)
- Full paths of source file(s) related to the issue
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Response Timeline

- **Initial response**: Within 48 hours
- **Status update**: Within 7 days
- **Fix timeline**: Depends on severity
  - Critical: Within 7 days
  - High: Within 30 days
  - Medium: Within 90 days
  - Low: Next release cycle

## Security Best Practices for Users

When deploying SVTR Bot, please follow these security practices:

### 🔑 API Key Hygiene

- ✅ **NEVER** commit your `.env` file to version control
- ✅ Use **read-only** API keys for market data when possible
- ✅ For trading keys, **disable withdrawal permissions** on the exchange side
- ✅ Set **IP whitelist** on your exchange API keys
- ✅ **Rotate keys** regularly (every 90 days recommended)
- ✅ Use a **dedicated sub-account** for the bot, not your main trading account

### 🌐 Network Security

- ✅ Run the bot on a **private VPS** (not your home network)
- ✅ Use **SSH key authentication** (disable password auth)
- ✅ Enable **firewall** (ufw/iptables) — only allow ports 22, 80, 443, 8000
- ✅ Use **HTTPS** for any public-facing endpoints (use a reverse proxy like nginx + Let's Encrypt)
- ✅ Set up **fail2ban** to prevent brute-force SSH attacks

### 🔒 Operational Security

- ✅ **Always start with `EXCHANGE_TESTNET=true`**
- ✅ Set **small position sizes** during initial testing
- ✅ Enable **Telegram kill switch** for emergency stops
- ✅ **Monitor logs** regularly for unexpected behavior
- ✅ Set up **Prometheus alerts** for error spikes or P&L anomalies
- ✅ **Backup** your `data/` and `logs/` directories regularly
- ✅ Use **Docker secrets** instead of environment variables in production

### 🛡️ Defense in Depth

The bot is designed with multiple security layers:

1. **API Key Isolation** — Read-only where possible, no withdrawal
2. **Runtime Safety** — Non-root Docker user, no privileged operations
3. **Risk Limits** — Circuit breaker, daily max loss, position size caps
4. **AI Override** — Claude can reject trades it deems risky
5. **Manual Kill Switch** — Telegram command for emergency shutdown

## Known Security Considerations

- **LLM Prompt Injection**: The Claude integration accepts contextual data
  (news, social media). A malicious actor could craft input designed to
  manipulate the AI's decisions. We mitigate this by:
  - Treating Claude's output as a *recommendation*, not a command
  - Requiring strong technical signals before AI can override
  - Logging all AI decisions for audit

- **Supply Chain**: We depend on:
  - `ccxt` (exchange connectivity)
  - `anthropic` SDK (Claude API)
  - `trading-agents` (TauricResearch/TradingAgents)
  - `agent-reach` CLI tools (subprocess execution)
  - All dependencies pinned with version ranges in `pyproject.toml`

- **Subprocess Execution**: `src/sentiment/social.py` calls
  `twitter-cli` and `rdt-cli` via subprocess. Only invoke this module
  on systems where you've reviewed Agent-Reach's source code.

## Acknowledgments

We'd like to thank the following people for responsibly disclosing security
issues (none reported yet — this list will be updated as issues are fixed):

*Your name could be here.*

## Security Updates

Security advisories will be published at:
https://github.com/Galdr1c/Trader000/security/advisories

To receive notifications, **Watch** this repository and enable
"Security alerts" notifications.

---

<p align="center">
  <sub>Security is a process, not a product.</sub>
</p>
