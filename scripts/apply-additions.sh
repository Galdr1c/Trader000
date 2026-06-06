#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# SVTR Bot — Apply Documentation & Configuration Additions
# ═══════════════════════════════════════════════════════════════════
# This script copies all the addition files (README, docs, configs)
# into the appropriate locations in your local Trader000 repository.
#
# Usage:
#   chmod +x scripts/apply-additions.sh
#   ./scripts/apply-additions.sh
#
# Prerequisites:
#   - You have a local clone of https://github.com/Galdr1c/Trader000
#   - You are in the repository root when running this script
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ── Helpers ─────────────────────────────────────────────────────────
info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
err()   { echo -e "${RED}✗${NC}  $*"; }

# ── Pre-flight checks ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDITIONS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Check we're in a git repo
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    err "Not in a git repository. Run this script from your Trader000 repo root."
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
info "Repository root: $REPO_ROOT"
info "Additions source: $ADDITIONS_DIR"

# Check the additions source has the expected files
if [[ ! -f "$ADDITIONS_DIR/README.md" ]]; then
    err "Additions package not found at $ADDITIONS_DIR/README.md"
    err "Make sure you extracted the additions package and are running from there."
    exit 1
fi

# ── Backup existing files (if any) ─────────────────────────────────
info "Backing up existing files (if any)..."
BACKUP_DIR="$REPO_ROOT/.additions-backup-$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

for file in README.md LICENSE CHANGELOG.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md; do
    if [[ -f "$REPO_ROOT/$file" ]]; then
        cp "$REPO_ROOT/$file" "$BACKUP_DIR/$file"
        warn "  backed up: $file"
    fi
done

# ── Copy files ─────────────────────────────────────────────────────
info "Copying files..."

# Top-level
[[ -f "$ADDITIONS_DIR/README.md"            ]] && cp "$ADDITIONS_DIR/README.md"            "$REPO_ROOT/README.md"            && ok "  README.md"
[[ -f "$ADDITIONS_DIR/LICENSE"              ]] && cp "$ADDITIONS_DIR/LICENSE"              "$REPO_ROOT/LICENSE"              && ok "  LICENSE"
[[ -f "$ADDITIONS_DIR/CHANGELOG.md"         ]] && cp "$ADDITIONS_DIR/CHANGELOG.md"         "$REPO_ROOT/CHANGELOG.md"         && ok "  CHANGELOG.md"
[[ -f "$ADDITIONS_DIR/CONTRIBUTING.md"      ]] && cp "$ADDITIONS_DIR/CONTRIBUTING.md"      "$REPO_ROOT/CONTRIBUTING.md"      && ok "  CONTRIBUTING.md"
[[ -f "$ADDITIONS_DIR/CODE_OF_CONDUCT.md"   ]] && cp "$ADDITIONS_DIR/CODE_OF_CONDUCT.md"   "$REPO_ROOT/CODE_OF_CONDUCT.md"   && ok "  CODE_OF_CONDUCT.md"
[[ -f "$ADDITIONS_DIR/SECURITY.md"          ]] && cp "$ADDITIONS_DIR/SECURITY.md"          "$REPO_ROOT/SECURITY.md"          && ok "  SECURITY.md"

# docs/
mkdir -p "$REPO_ROOT/docs"
for f in "$ADDITIONS_DIR/docs/"*.md; do
    [[ -f "$f" ]] && cp "$f" "$REPO_ROOT/docs/$(basename "$f")" && ok "  docs/$(basename "$f")"
done

# deploy/
mkdir -p "$REPO_ROOT/deploy/prometheus"
mkdir -p "$REPO_ROOT/deploy/grafana/dashboards"
[[ -f "$ADDITIONS_DIR/deploy/prometheus/prometheus.yml" ]] && \
    cp "$ADDITIONS_DIR/deploy/prometheus/prometheus.yml" "$REPO_ROOT/deploy/prometheus/prometheus.yml" && \
    ok "  deploy/prometheus/prometheus.yml"
[[ -f "$ADDITIONS_DIR/deploy/grafana/dashboards/svtr-bot.json" ]] && \
    cp "$ADDITIONS_DIR/deploy/grafana/dashboards/svtr-bot.json" "$REPO_ROOT/deploy/grafana/dashboards/svtr-bot.json" && \
    ok "  deploy/grafana/dashboards/svtr-bot.json"

# .github/
mkdir -p "$REPO_ROOT/.github/workflows"
mkdir -p "$REPO_ROOT/.github/ISSUE_TEMPLATE"
[[ -f "$ADDITIONS_DIR/.github/workflows/ci.yml" ]] && \
    cp "$ADDITIONS_DIR/.github/workflows/ci.yml" "$REPO_ROOT/.github/workflows/ci.yml" && \
    ok "  .github/workflows/ci.yml"
for f in "$ADDITIONS_DIR/.github/ISSUE_TEMPLATE/"*.md; do
    [[ -f "$f" ]] && cp "$f" "$REPO_ROOT/.github/ISSUE_TEMPLATE/$(basename "$f")" && ok "  .github/ISSUE_TEMPLATE/$(basename "$f")"
done

# ── Summary ────────────────────────────────────────────────────────
echo ""
ok "All files copied successfully!"
echo ""
info "Files added:"
echo "  - README.md (replaces existing if any)"
echo "  - LICENSE (MIT)"
echo "  - CHANGELOG.md"
echo "  - CONTRIBUTING.md"
echo "  - CODE_OF_CONDUCT.md"
echo "  - SECURITY.md"
echo "  - docs/ARCHITECTURE.md"
echo "  - docs/QUICKSTART.md"
echo "  - deploy/prometheus/prometheus.yml"
echo "  - deploy/grafana/dashboards/svtr-bot.json"
echo "  - .github/workflows/ci.yml"
echo "  - .github/ISSUE_TEMPLATE/bug_report.md"
echo "  - .github/ISSUE_TEMPLATE/feature_request.md"
echo ""
info "Backups (if any) saved to: $BACKUP_DIR"
echo ""

# ── Next steps hint ────────────────────────────────────────────────
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Review the changes:"
echo "     git status"
echo "     git diff --stat"
echo ""
echo "  2. Stage and commit:"
echo "     git add ."
echo "     git commit -m \"docs: add comprehensive README, architecture, CI, and monitoring config\""
echo ""
echo "  3. Push to GitHub:"
echo "     git push origin main"
echo ""
echo "  4. Verify on GitHub:"
echo "     - README should render nicely"
echo "     - CI workflow should run on push"
echo "     - Issue templates should appear in 'New Issue'"
echo ""
