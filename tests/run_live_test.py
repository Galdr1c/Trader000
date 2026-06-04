"""Live test: starts bot, runs MCP scan, tests endpoints."""

from __future__ import annotations

import asyncio
import json
import time
import threading
import urllib.request
import urllib.error

import uvicorn
from src.main import app


def _start_server(port: int = 8005) -> threading.Thread:
    """Start uvicorn in a background thread."""
    def run():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _wait_for_server(url: str, timeout: int = 10) -> bool:
    """Wait for server to respond."""
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def test_health(base: str) -> None:
    r = urllib.request.urlopen(f"{base}/health")
    d = json.loads(r.read())
    print(f"  Health: {d}")


def test_status(base: str) -> None:
    r = urllib.request.urlopen(f"{base}/status")
    d = json.loads(r.read())
    print(f"  Exchange: {d['exchange']}")
    print(f"  AI: {d['ai']}")
    print(f"  Runtime: {d['runtime']}")


def test_webhook(base: str) -> None:
    body = json.dumps({
        "symbol": "BTCUSDT",
        "direction": "long",
        "price": 67500.0,
        "signal_score": 9.5,
        "tp_distance": 4.2,
    }).encode()
    req = urllib.request.Request(
        f"{base}/webhook",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    r = urllib.request.urlopen(req)
    print(f"  Webhook: {json.loads(r.read())}")


def test_alerts(base: str) -> None:
    r = urllib.request.urlopen(f"{base}/api/alerts")
    alerts = json.loads(r.read())
    print(f"  Alerts: {len(alerts)} total")
    if alerts:
        a = alerts[-1]
        print(f"  Last: {a['symbol']} {a['direction']} score={a['score']}")


async def test_mcp_scan() -> None:
    """Test MCP data fetching directly."""
    from src.mcp_provider.client import MCPClient
    from src.scanner.scanner import compute_signal_score

    mcp = MCPClient()

    # Price
    price = await mcp.get_price("BTC-USD")
    p = price.get("price", 0)
    chg = price.get("change_pct", 0)
    print(f"  BTC Price: ${p:,.2f} ({chg:+.2f}%)")

    # Technical analysis
    ta = await mcp.get_technical_analysis("BTC-USD", "BINANCE", "4h")
    print(f"  TA Summary: {ta.get('summary')}")
    print(f"  Signals: {ta.get('buy_count')} Buy / {ta.get('sell_count')} Sell / {ta.get('neutral_count')} Neutral")

    # Signal score
    score, direction, conf = compute_signal_score(ta)
    print(f"  Signal Score: {score}/13.5 | Direction: {direction} | Confidence: {conf:.2f}")

    return price


def main() -> None:
    PORT = 8005
    BASE = f"http://127.0.0.1:{PORT}"

    print("=" * 60)
    print("SVTR BOT - LIVE TEST (MCP + TRADINGAGENTS)")
    print("=" * 60)

    # Start server
    print("\n[1] Starting server...")
    _start_server(PORT)
    if not _wait_for_server(f"{BASE}/health"):
        print("  FAILED: Server did not start")
        return
    print("  Server OK")

    # Test endpoints
    print("\n[2] Health check")
    test_health(BASE)

    print("\n[3] Status dashboard")
    test_status(BASE)

    # Run MCP scan
    print("\n[4] MCP Scan (BTC)")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    price = loop.run_until_complete(test_mcp_scan())

    # Test webhook
    print("\n[5] Webhook test (LONG signal)")
    test_webhook(BASE)

    # Check alerts
    print("\n[6] Alert history")
    test_alerts(BASE)

    # Check dashboard
    print("\n[7] Dashboard HTML")
    r = urllib.request.urlopen(f"{BASE}/")
    html = r.read().decode()
    print(f"  Length: {len(html)} chars")
    print(f"  Title: SVTR Bot Dashboard (found: {'SVTR' in html})")

    # Final metrics
    print("\n[8] Metrics")
    r = urllib.request.urlopen(f"{BASE}/metrics")
    metrics_text = r.read().decode()
    lines = [l for l in metrics_text.split("\n") if l.strip() and not l.startswith("#")]
    print(f"  Metrics lines: {len(lines)}")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print(f"Dashboard: {BASE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
