"""End-to-end webhook test — simulates TradingView alert flow."""

import asyncio
import sys

from httpx import AsyncClient, ASGITransport

from src.webhook.server import create_app

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

app = create_app()
transport = ASGITransport(app=app)


async def test_long_entry_json():
    """Test LONG entry alert via JSON (TradingView webhook format)."""
    payload = {
        "symbol": "BTCUSDT",
        "direction": "long",
        "price": 67500.00,
        "signal_score": 9.5,
        "tp_distance": 4.2,
        "adx_trend": "strong",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", json=payload)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        body = r.json()
        assert body["signal_score"] == 9.5, f"Score mismatch: {body}"
        assert body["symbol"] == "BTCUSDT", f"Symbol mismatch: {body}"
        print("[PASS] LONG JSON entry")
        return body


async def test_short_entry_json():
    """Test SHORT entry alert via JSON."""
    payload = {
        "symbol": "ETHUSDT",
        "direction": "short",
        "price": 3500.00,
        "signal_score": 8.2,
        "tp_distance": 3.5,
        "adx_trend": "weak",
    }
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["signal_score"] == 8.2
        assert body["symbol"] == "ETHUSDT", f"Symbol mismatch: {body}"
        print("[PASS] SHORT JSON entry")
        return body


async def test_long_entry_text():
    """Test LONG entry alert via plain text (Pine Script alert format)."""
    text = (
        "LONG ENTRY\n"
        "Symbol: BTCUSDT\n"
        "Price: 67500.00\n"
        "Signal Score: 9.5/13.5\n"
        "TP Distance: 4.2%\n"
        "ADX Trend: Strong"
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            content=text.encode(),
            headers={"content-type": "text/plain"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["signal_score"] == 9.5
        assert body["symbol"] == "BTCUSDT"
        print("[PASS] LONG text entry (Pine Script format)")
        return body


async def test_health_check():
    """Test health endpoint."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        print(f"[PASS] Health check (engine={body['engine']})")
        return body


async def test_missing_symbol():
    """Test missing symbol returns 400."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", json={"direction": "long", "price": 100})
        assert r.status_code == 400
        print("[PASS] Missing symbol -> 400")
        return r.json()


async def test_empty_body():
    """Test empty body returns 400."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", content=b"")
        assert r.status_code == 400
        print("[PASS] Empty body -> 400")
        return r.json()


async def test_low_score():
    """Test low score alert is accepted but engine rejects."""
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json={"symbol": "BTCUSDT", "direction": "long", "price": 67500, "signal_score": 5.0},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["signal_score"] == 5.0
        assert body["symbol"] == "BTCUSDT", f"Symbol mismatch: {body}"
        print("[PASS] Low score returns parsed score")
        return body


async def run_all():
    """Run all tests."""
    tests = [
        test_health_check,
        test_long_entry_json,
        test_short_entry_json,
        test_long_entry_text,
        test_missing_symbol,
        test_empty_body,
        test_low_score,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed}/{passed + failed} passed, {failed} failed")
    print(f"{'=' * 40}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
