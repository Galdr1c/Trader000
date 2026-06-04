"""Test script — sends TradingView-style webhook alerts to the bot.

Simulates both JSON and plain-text TradingView webhook alerts.
Run this while the bot is running (python -m src.main).

Usage:
    python tests/test_send_alert.py              # JSON format
    python tests/test_send_alert.py --text        # Pine Script text format
    python tests/test_send_alert.py --low-score   # Low score test
    python tests/test_send_alert.py --all         # Run all tests
"""

import argparse, json, sys, time
from datetime import datetime, timezone

try:
    import httpx
except ImportError:
    print("pip install httpx"); sys.exit(1)

BASE = "http://localhost:8000"


def send_alert(payload: dict, description: str = "") -> dict:
    """Send a webhook alert and print the result."""
    r = httpx.post(f"{BASE}/webhook", json=payload, timeout=10)
    body = r.json()
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    status = "✅" if r.status_code == 200 else "❌"
    print(f"{status} [{ts}] {description}")
    print(f"   Status: {r.status_code} | Score: {body.get('signal_score', '?')}")
    print(f"   Action: {body.get('action_taken', '?')} | Msg: {body.get('message', '')[:60]}")
    if description:
        print(f"   Symbol: {body.get('symbol', '?')} | Direction: {payload.get('direction', '?')}")
    print()
    return body


def check_health() -> dict:
    """Check bot is running."""
    r = httpx.get(f"{BASE}/health", timeout=5)
    return r.json()


def check_alerts() -> list:
    """Fetch alert history from bot."""
    r = httpx.get(f"{BASE}/api/alerts", timeout=5)
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Send test TradingView webhooks")
    parser.add_argument("--text", action="store_true", help="Send plain-text alert")
    parser.add_argument("--low-score", action="store_true", help="Send low-score test")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--count", type=int, default=1, help="Number of alerts to send")
    args = parser.parse_args()

    print("=" * 60)
    print(f"SVTR Bot — Webhook Test at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Health check first
    try:
        health = check_health()
        print(f"\n✅ Bot is alive — {health.get('status', '?')} ({health.get('uptime_seconds', 0):.0f}s uptime)\n")
    except Exception as e:
        print(f"❌ Cannot connect to bot at {BASE}: {e}")
        print("   Make sure 'python -m src.main' is running in another terminal.")
        sys.exit(1)

    # Determine which tests to run
    run_all = args.all or not (args.text or args.low_score)

    if run_all or not (args.text or args.low_score):
        # ── Test 1: LONG Entry ────────────────────────────────────
        send_alert({
            "symbol": "BTCUSDT",
            "direction": "long",
            "price": 67500.00,
            "signal_score": 9.5,
            "tp_distance": 4.2,
            "adx_trend": "strong",
        }, "LONG Entry (BTC, score=9.5)")

    if run_all or args.low_score:
        # ── Test 2: Low Score (should be rejected) ────────────────
        send_alert({
            "symbol": "BTCUSDT",
            "direction": "long",
            "price": 68000.00,
            "signal_score": 3.0,
            "tp_distance": 2.0,
        }, "LOW Score (3.0 — should reject)")

    if run_all or not (args.text or args.low_score):
        # ── Test 3: SHORT Entry ───────────────────────────────────
        send_alert({
            "symbol": "ETHUSDT",
            "direction": "short",
            "price": 3500.00,
            "signal_score": 8.2,
            "tp_distance": 3.5,
        }, "SHORT Entry (ETH, score=8.2)")

    if run_all or args.text:
        # ── Test 4: Plain text (Pine Script format) ───────────────
        text_payload = (
            "LONG ENTRY\n"
            "Symbol: BTCUSDT\n"
            "Price: 67500.00\n"
            "Signal Score: 9.5/13.5\n"
            "TP Distance: 4.2%\n"
            "ADX Trend: Strong"
        )
        r = httpx.post(f"{BASE}/webhook", content=text_payload.encode(),
                       headers={"Content-Type": "text/plain"}, timeout=10)
        body = r.json()
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        status = "✅" if r.status_code == 200 else "❌"
        print(f"{status} [{ts}] Pine Script Text Alert")
        print(f"   Status: {r.status_code} | Score: {body.get('signal_score', '?')} | Symbol: {body.get('symbol', '?')}")
        print()

    # ── Show alert history from dashboard ────────────────────────
    time.sleep(1)
    alerts = check_alerts()
    print(f"\n📊 Total alerts in history: {len(alerts)}")
    for a in alerts[-5:]:
        print(f"   {a['time'][11:19]} | {a['direction']:>5} | {a['symbol']:<8} | score={a['score']} | {a['action']}")

    # ── Show final status ────────────────────────────────────────
    status = httpx.get(f"{BASE}/status", timeout=5).json()
    proc = status.get("runtime", {}).get("alerts_processed", 0)
    uptime = status.get("runtime", {}).get("uptime_seconds", 0)
    print(f"\n📈 Bot status: {proc} alerts processed, {uptime:.0f}s uptime")
    print("=" * 60)
    print("✅ Dashboard at http://localhost:8000 — refresh to see alerts!")


if __name__ == "__main__":
    main()
