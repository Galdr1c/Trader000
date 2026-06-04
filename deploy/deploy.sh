#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# SVTR Bot — VPS Deployment Script
# ═══════════════════════════════════════════════════════════════════════
# Usage:
#   chmod +x deploy/deploy.sh
#   ./deploy/deploy.sh          # Deploy all services
#   ./deploy/deploy.sh bot      # Deploy bot only
#   ./deploy/deploy.sh down     # Stop all services
#   ./deploy/deploy.sh logs     # Follow bot logs
#   ./deploy/deploy.sh status   # Show service status
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[SVTR]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }

# ── Pre-flight checks ──────────────────────────────────────────────
preflight() {
    log "Running pre-flight checks..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        err "Docker not found. Install: https://docs.docker.com/engine/install/"
        exit 1
    fi

    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        err "Docker Compose not found."
        exit 1
    fi

    # Check .env file
    if [ ! -f .env ]; then
        warn ".env file not found. Copying from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            warn "⚠️  Edit .env with your API keys before starting!"
            exit 1
        else
            err "No .env or .env.example found."
            exit 1
        fi
    fi

    # Validate required env vars
    local required_vars=(
        "EXCHANGE_API_KEY"
        "EXCHANGE_SECRET"
        "ANTHROPIC_API_KEY"
    )

    for var in "${required_vars[@]}"; do
        val=$(grep -E "^${var}=" .env | cut -d'=' -f2)
        if [ -z "$val" ] || [ "$val" = "your_api_key_here" ] || [ "$val" = "your_secret_here" ] || [ "$val" = "your_anthropic_key_here" ]; then
            err "$var is not set or still has placeholder value. Edit .env"
            exit 1
        fi
    done

    log "Pre-flight checks passed ✅"
}

# ── Create directories ─────────────────────────────────────────────
setup_dirs() {
    mkdir -p data logs
    chmod 755 data logs
}

# ── Deploy ──────────────────────────────────────────────────────────
deploy_all() {
    preflight
    setup_dirs

    log "Building and starting all services..."
    docker compose up -d --build

    log "Waiting for health check..."
    sleep 5

    # Health check
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "✅ Bot is healthy!"
    else
        warn "Bot not responding yet (may need more time to start)"
    fi

    echo ""
    log "Services running:"
    docker compose ps
    echo ""
    log "Endpoints:"
    log "  Bot:      http://localhost:8000"
    log "  Health:   http://localhost:8000/health"
    log "  Status:   http://localhost:8000/status"
    log "  Metrics:  http://localhost:8000/metrics"
    log "  Grafana:  http://localhost:3000 (admin/svtr-bot-2024)"
    log "  Prometheus: http://localhost:9090"
}

deploy_bot_only() {
    preflight
    setup_dirs

    log "Building and starting bot only..."
    docker compose up -d --build svtr-bot

    sleep 3
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log "✅ Bot is healthy!"
    else
        warn "Bot may still be starting..."
    fi
}

stop_all() {
    log "Stopping all services..."
    docker compose down
    log "All services stopped ✅"
}

show_logs() {
    docker compose logs -f svtr-bot
}

show_status() {
    docker compose ps
    echo ""
    # Health check
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "Bot Health: ✅ OK"
        curl -s http://localhost:8000/status | python -m json.tool 2>/dev/null || true
    else
        echo "Bot Health: ❌ Not responding"
    fi
}

# ── Main ────────────────────────────────────────────────────────────
case "${1:-all}" in
    all)    deploy_all ;;
    bot)    deploy_bot_only ;;
    down)   stop_all ;;
    logs)   show_logs ;;
    status) show_status ;;
    *)
        echo "Usage: $0 {all|bot|down|logs|status}"
        exit 1
        ;;
esac
