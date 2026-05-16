#!/usr/bin/env bash
# =============================================================
# deploy.sh - Build and deploy CondenseIt to your VPS
#
# Builds the frontend SPA, packages a wheel, rsyncs everything
# to the VPS, and restarts the condenseit-web systemd service.
#
# Usage:
#   ./scripts/deploy.sh              # full build + deploy
#   ./scripts/deploy.sh --skip-build # rsync only, no rebuild
#   ./scripts/deploy.sh --sync-db    # also push local DB to VPS
#                                    # (DANGER: overwrites production data)
#
# One-time VPS setup: ./scripts/bootstrap-server.sh
#
# Required env (set in .env or environment):
#   DIGEST_PWA_SSH_HOST  - SSH target (e.g. "user@1.2.3.4" or ~/.ssh/config alias)
#   DIGEST_PWA_DOMAIN    - Domain name for nginx (e.g. "digest.example.com")
#
# Optional:
#   DIGEST_PWA_REMOTE_DIR    - Override static file path (default: /var/www/$DOMAIN)
#   DIGEST_PWA_LIVE_URL      - Override smoke test URL (default: https://$DOMAIN)
#   CONDENSEIT_VPS_PORT      - FastAPI port (default: 8765)
#   CONDENSEIT_VPS_DATA_DIR  - Data dir on VPS (default: ~/condenseit/data)
#   CONDENSEIT_AUTH_PASSWORD - App auth password (for smoke test)
# =============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load .env from repo root.
if [[ -f "$ROOT/.env" ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +o allexport
fi

# shellcheck source=lib/vps-from-config.sh
source "$ROOT/scripts/lib/vps-from-config.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }
die()  { echo -e "${RED}[deploy] ERROR:${NC} $*" >&2; exit 1; }

SKIP_BUILD=false
SYNC_DB=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=true ;;
    --sync-db)    SYNC_DB=true ;;
    --help|-h)
      sed -n '3,22p' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) die "Unknown option: $arg" ;;
  esac
done

# ---------------------------------------------------------------------------
# Resolve SSH target and paths
# ---------------------------------------------------------------------------
CONFIG_HOST=""
CONFIG_PATH=""
CONFIG_DIGEST_URL=""
CONFIG_DOMAIN=""
vps_from_config || die "Failed to read vps.* from config.yaml (run: uv sync)"

SSH_HOST="${DIGEST_PWA_SSH_HOST:-${CONFIG_HOST:-}}"
[[ -n "$SSH_HOST" ]] || SSH_HOST="digest-vps"

DOMAIN="${DIGEST_PWA_DOMAIN:-$CONFIG_DOMAIN}"

REMOTE_DIR="${DIGEST_PWA_REMOTE_DIR:-}"
if [[ -z "$REMOTE_DIR" ]]; then
  REMOTE_DIR="${CONFIG_PATH:-/var/www/${DOMAIN:-condenseit}}"
fi
REMOTE_DIR="${REMOTE_DIR%/}"

LIVE_URL="${DIGEST_PWA_LIVE_URL:-}"
if [[ -z "$LIVE_URL" ]]; then
  LIVE_URL="${CONFIG_DIGEST_URL:-https://${DOMAIN:-localhost}}"
fi
LIVE_URL="${LIVE_URL%/}"

VPS_SERVICE="condenseit-web"
VPS_SERVICE_PORT="${CONDENSEIT_VPS_PORT:-8765}"
VPS_DATA_DIR="${CONDENSEIT_VPS_DATA_DIR:-\$HOME/condenseit/data}"

info "Target: $SSH_HOST:$REMOTE_DIR"

command -v rsync &>/dev/null || die "rsync not found"

ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" true 2>/dev/null \
  || die "Cannot SSH to '$SSH_HOST'. Set DIGEST_PWA_SSH_HOST or vps.host in config.yaml."

# ---------------------------------------------------------------------------
# Build frontend
# ---------------------------------------------------------------------------
if [[ "$SKIP_BUILD" == false ]]; then
  info "Building frontend SPA..."
  FRONTEND_DIR="$ROOT/frontend"
  if [[ -f "$FRONTEND_DIR/package.json" ]]; then
    (
      cd "$FRONTEND_DIR"
      if ! command -v node &>/dev/null; then
        die "node not found. Install Node.js to build the frontend."
      fi
      npm ci --silent
      npm run build
    ) || die "Frontend build failed"
  else
    die "frontend/package.json not found."
  fi
fi

FRONTEND_DIST="$ROOT/frontend/dist"
[[ -d "$FRONTEND_DIST" ]] || die "Missing $FRONTEND_DIST (run: cd frontend && npm run build)"

# ---------------------------------------------------------------------------
# Build and upload condenseit wheel
# ---------------------------------------------------------------------------
command -v uv &>/dev/null || die "uv not found. Install with: pip install uv"

WHEEL_DIR="$(mktemp -d)"
trap 'rm -rf "$WHEEL_DIR"' EXIT

info "Building condenseit wheel..."
(cd "$ROOT" && uv build --wheel --out-dir "$WHEEL_DIR" --quiet) \
  || die "uv build failed."

WHEEL_FILE="$(ls "$WHEEL_DIR"/condenseit-*.whl 2>/dev/null | head -1)"
[[ -n "$WHEEL_FILE" ]] || die "No wheel found after uv build."
WHEEL_BASENAME="$(basename "$WHEEL_FILE")"

info "Uploading $WHEEL_BASENAME to VPS..."
scp -q "$WHEEL_FILE" "$SSH_HOST:/tmp/$WHEEL_BASENAME"

info "Installing $WHEEL_BASENAME on VPS..."
ssh "$SSH_HOST" WHEEL_BASENAME="$WHEEL_BASENAME" bash <<'REMOTE_INSTALL'
set -euo pipefail
APP_DIR="$HOME/condenseit"
if [[ ! -x "$APP_DIR/.venv/bin/pip" ]]; then
  echo "Missing $APP_DIR/.venv/bin/pip; run scripts/bootstrap-server.sh first." >&2
  exit 1
fi
"$APP_DIR/.venv/bin/pip" install --quiet --force-reinstall "/tmp/$WHEEL_BASENAME"
rm -f "/tmp/$WHEEL_BASENAME"
echo "Installed OK."
REMOTE_INSTALL

# ---------------------------------------------------------------------------
# Stop service before DB + static sync
# ---------------------------------------------------------------------------
info "Stopping $VPS_SERVICE on VPS..."
ssh "$SSH_HOST" "sudo systemctl stop $VPS_SERVICE 2>/dev/null || true"

# ---------------------------------------------------------------------------
# Rsync SQLite DB (opt-in only -- requires --sync-db flag)
# ---------------------------------------------------------------------------
# DB sync is intentionally skipped by default to avoid overwriting production
# data with a local copy. Pass --sync-db only when you explicitly want to
# replace the production database (e.g. seeding a fresh VPS from scratch).
LOCAL_DB="$ROOT/data/condenseit.db"
if [[ "$SYNC_DB" == true ]]; then
  if [[ -f "$LOCAL_DB" ]]; then
    warn "WARNING: --sync-db is set. This will OVERWRITE the production database."
    warn "Press Ctrl-C within 5 seconds to abort..."
    sleep 5
    info "Syncing SQLite DB to VPS..."
    VPS_DATA_DIR_REAL="$(ssh "$SSH_HOST" "echo $VPS_DATA_DIR")"
    ssh "$SSH_HOST" "mkdir -p '$VPS_DATA_DIR_REAL'"
    rsync -avz "$LOCAL_DB" "$SSH_HOST:$VPS_DATA_DIR_REAL/condenseit.db"
  else
    warn "Local DB not found at $LOCAL_DB; skipping DB rsync."
  fi
else
  info "Skipping DB sync (pass --sync-db to overwrite the production database)."
fi

# ---------------------------------------------------------------------------
# Rsync static SPA files
# ---------------------------------------------------------------------------
info "Rsyncing frontend/dist to $SSH_HOST:$REMOTE_DIR ..."
ssh "$SSH_HOST" "sudo mkdir -p '$REMOTE_DIR' && sudo chown -R \"\$USER:www-data\" '$REMOTE_DIR' && chmod -R g+rX '$REMOTE_DIR'"
rsync -avz --delete \
  "$FRONTEND_DIST/" \
  "$SSH_HOST:$REMOTE_DIR/"

# ---------------------------------------------------------------------------
# Restart service
# ---------------------------------------------------------------------------
info "Starting $VPS_SERVICE on VPS..."
if ssh "$SSH_HOST" "sudo systemctl start $VPS_SERVICE"; then
  info "$VPS_SERVICE started."
else
  warn "$VPS_SERVICE failed to start. Check: ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -n 50'"
fi

# ---------------------------------------------------------------------------
# Reload nginx
# ---------------------------------------------------------------------------
info "Reloading nginx..."
if ssh "$SSH_HOST" "command -v nginx >/dev/null 2>&1"; then
  ssh "$SSH_HOST" "sudo nginx -t && sudo systemctl reload nginx" \
    || warn "nginx reload failed; check sudoers or run manually."
else
  warn "nginx not found on remote; skipped."
fi

# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------
info "Smoke check..."
_COOKIE_JAR="$(mktemp /tmp/condenseit_smoke_XXXXXX.txt)"
_AUTH_PW="${CONDENSEIT_AUTH_PASSWORD:-${DIGEST_PWA_AUTH_PASSWORD:-}}"

if [[ -n "$_AUTH_PW" ]]; then
  curl -sS -c "$_COOKIE_JAR" \
    -X POST "${LIVE_URL}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"password\":\"${_AUTH_PW}\"}" \
    -o /dev/null \
    || warn "Smoke login request failed."
fi

code=$(curl -sL -b "$_COOKIE_JAR" -o /dev/null -w '%{http_code}' "${LIVE_URL}/" || echo "000")
rm -f "$_COOKIE_JAR"

if [[ "$code" == "200" ]]; then
  info "HTTP $code for $LIVE_URL"
else
  warn "HTTP $code for $LIVE_URL (TLS or first deploy may still be in progress)"
fi

echo ""
info "Done. Live URL: $LIVE_URL"
