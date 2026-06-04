# SVTR Bot — VPS Deployment Guide (Phase 4)

## Hızlı Başlangıç (5 Adım)

### 1. Sunucu Gereksinimleri

| Kaynak | Minimum | Önerilen |
|--------|---------|----------|
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 10 GB | 20 GB SSD |
| OS | Ubuntu 22.04+ / Debian 12+ | |
| Docker | 24.0+ | |
| Docker Compose | v2.20+ | |

### 2. Sunucu Hazırlığı

```bash
# SSH ile bağlan
ssh root@YOUR_VPS_IP

# Docker kur
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Docker Compose (genelde Docker ile birlikte gelir)
docker compose version
```

### 3. Kodu Klonla ve Ayarla

```bash
# Kodu klonla
git clone https://github.com/YOUR_USER/svtr-bot.git
cd svtr-bot

# .env oluştur ve doldur
cp .env.example .env
nano .env  # API key'leri gir
```

**Zorunlu Environment Değişkenleri:**
```env
EXCHANGE_API_KEY=your_key
EXCHANGE_SECRET=your_secret
EXCHANGE_TESTNET=true          # İlk testler için true!
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123:ABC
TELEGRAM_CHAT_ID=-100xxx
WEBHOOK_SECRET=random_secret   # HMAC doğrulama için
```

### 4. Deploy Et

```bash
chmod +x deploy/deploy.sh

# Tüm servisleri başlat (bot + redis + prometheus + grafana)
./deploy/deploy.sh all

# Vade sadece bot
./deploy/deploy.sh bot
```

### 5. Doğrula

```bash
# Servis durumunu kontrol et
./deploy/deploy.sh status

# Health check
curl http://localhost:8000/health

# Detaylı sistem durumu
curl http://localhost:8000/status

# Prometheus metrikleri
curl http://localhost:8000/metrics
```

---

## Servisler ve Portlar

| Servis | Port | URL | Açıklama |
|--------|------|-----|----------|
| SVTR Bot | 8000 | http://YOUR_IP:8000 | Webhook + API |
| Grafana | 3000 | http://YOUR_IP:3000 | Dashboard (admin/svtr-bot-2024) |
| Prometheus | 9090 | http://YOUR_IP:9090 | Metrikler |
| Redis | 6379 | localhost | State cache (dışarıya açık değil) |

---

## TradingView Webhook Ayarı

1. Bot public URL'e ihtiyacınız var:
```bash
# nginx reverse proxy (önerilen)
apt install nginx
# /etc/nginx/sites-available/svtr-bot:
```

```nginx
server {
    listen 443 ssl;
    server_name trading.YOUR_DOMAIN.com;

    ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

2. TradingView'da webhook URL'ini ayarla:
```
https://trading.YOUR_DOMAIN.com/webhook
```

---

## Güvenlik Kontrol Listesi

- [ ] `.env` dosyası 600 izni ile: `chmod 600 .env`
- [ ] `EXCHANGE_TESTNET=true` ile başla
- [ ] API key'lerde sadece trade izni var (para çekme yok)
- [ ] `WEBHOOK_SECRET` rastgele üretilmiş
- [ ] Firewall: sadece 80, 443, 22 açık
- [ ] Grafana şifresi değiştirilmiş
- [ ] Redis dışarıya açık değil (sadece Docker network)

---

## Yönetim Komutları

```bash
# Logları takip et
./deploy/deploy.sh logs

# Servisleri yeniden başlat
docker compose restart svtr-bot

# Yeni kod ile güncelle
git pull
docker compose up -d --build svtr-bot

# Prometheus veri temizleme
docker compose exec prometheus rm -rf /prometheus/*

# Tamamen durdur
./deploy/deploy.sh down

# Backup (data + logs)
tar -czf svtr-backup-$(date +%Y%m%d).tar.gz data/ logs/ .env
```

---

## Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| Bot başlamıyor | `docker compose logs svtr-bot` — API key kontrol |
| Webhook 401 | `WEBHOOK_SECRET` TradingView ile eşleşmeli |
| Redis bağlantı hatası | `docker compose restart redis` |
| Grafana boş dashboard | `docker compose restart grafana` |
| Disk dolu | `docker system prune -a` — eski image'ları temizle |
| High memory | `docker compose down && docker compose up -d` — restart |

---

## Production Önerileri

1. **Önce testnet ile test et** — en az 1 ay paper trading
2. **Günlük kayıp limitini %2-3'te tut** — `%5` agresif
3. **Pozisyon başına max %5 equity** — tek trade'de iflas etme
4. **Circuit breaker test et** — 3 ardışık stop → cooldown
5. **Telegram'dan durdurma** — `/stop` komutu ekle
6. **Grafana alert kur** — bot down, yüksek kayıp, extreme funding
7. **Log rotation** — `logrotate` ile logs/ klasörünü yönet
8. **Otomatik backup** — cron ile günlük tar.gz
