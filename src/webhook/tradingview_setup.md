# TradingView Webhook Kurulum Rehberi

## 1. Webhook URL'ini Ayarla

TradingView, webhook alert'leri sadece **HTTPS** URL'lerine gönderebilir.
Local development için **ngrok** kullanacağız:

```bash
# Ngrok'u kur (bir kez)
# https://ngrok.com/download adresinden indir ve PATH'e ekle

# Sunucuyu başlat (Terminal 1)
cd svtr-bot
python -m src.main

# Ngrok tunnel aç (Terminal 2)
ngrok http 8000
```

Ngrok size bir URL verir: `https://xxxx-xx-xx-xx-xx.ngrok-free.app`
Bu URL'i TradingView'da kullanacaksın.

## 2. Pine Script'te Alert Mesajı Oluştur

TradingView webhook mesaj alanı sadece **plain text** destekler.
**JSON template variable'ları çalışmaz.**doğru yol Pine Script'te `alert()` fonksiyonu kullanmaktır.

SVTR Pine Script'indeki `alert()` fonksiyonları zaten doğru formatta — sadece alert'i aktif etmen yeterli.

### Eğer özel mesaj yazmak istersen:

Pine Script'te şöyle bir `alert()` kullan:

```pine
alert("🟢 LONG ENTRY\nSymbol: " + syminfo.ticker + "\nPrice: " + str.tostring(close, format.mintick) + "\nSignal Score: " + str.tostring(entrySignalScore, "#.#") + "/13.5\nTP Distance: " + str.tostring(dynamicTPDistance, "#.#") + "%\nADX Trend: " + (g_bullishAlignment ? "✅ Strong" : "⚠ Weak"), alert.freq_once_per_bar)
```

Bu mesaj webhook'a plain text olarak gider, bizim `TVAlertPayload.from_text()` tarafından parse edilir.

## 3. TradingView'da Alert Oluştur

1. TradingView'da stratejini aç (SVTR Ultimate v3.8)
2. Sağ üstteki **Clock icon** → **Create Alert** (veya `Alt+Shift+A`)
3. Alert ayarlarını configured et:

| Alan | Değer |
|------|-------|
| **Condition** | SVTR Ultimate v3.8 |
| **Alert name** | SVTR Signal |
| **Message** | Pine Script'teki alert() mesajını kullan (veya boş bırak — alert() otomatik doldurur) |
| **Webhook URL** | `https://xxxx-xx-xx-xx-xx.ngrok-free.app/webhook` |
| **Send email** | ❌ Kapat |
| **Show pop-up** | ❌ Kapat |

## 4. Pine Script'te Alert Aktif Et

SVTR Pine Script'ine `alert()` fonksiyonları zaten ekli:

```
🔔 Notification Settings
├── Enable Entry Notifications ✅
├── Alert on Position Entry ✅
├── Alert on TP Levels ✅
└── Alert on Position Exit ✅
```

Bu ayarları aktif et, TradingView otomatik olarak webhook'a alert gönderecek.

## 5. Manuel Test (curl)

Sunucu çalışırken test edebilirsin:

```bash
# LONG sinyal testi
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "direction": "long",
    "price": 67500.00,
    "signal_score": 9.5,
    "tp_distance": 4.2,
    "adx_trend": "strong"
  }'

# SHORT sinyal testi
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSDT",
    "direction": "short",
    "price": 3500.00,
    "signal_score": 8.2,
    "tp_distance": 3.5,
    "adx_trend": "weak"
  }'

# Health check
curl http://localhost:8000/health
```

## 6. Otomatik Test

```bash
PYTHONPATH=. python tests/test_e2e_webhook.py
```

## 7. Production Deploy (VPS)

ngrok sadece development içindir. Production'da:

1. **VPS'e deploy et** (Docker Compose ile)
2. **Cloudflare Tunnel** veya **Caddy reverse proxy** ile HTTPS ekle
3. TradingView webhook URL'ini production URL'ine güncelle
4. **Webhook Secret** ayarla (HMAC verification için)

```bash
# VPS'te
docker-compose up -d
# Caddy otomatik SSL sertifikası alır
```

## 8. Güvenlik

- Webhook secret kullan (`.env` dosyasında `WEBHOOK_SECRET`)
- API key'lerini asla commit etme
- Binance API key: sadece trade izni, para çekme YOK
- IP whitelist (Binance panelinden)
