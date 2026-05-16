#!/usr/bin/env bash
# =============================================================
# bootstrap-server.sh - One-time VPS setup for full CondenseIt service
#
# Runs from your LOCAL machine over SSH and:
#   1. Creates ~/condenseit/.venv and installs condenseit
#   2. Creates ~/condenseit/.env with your secrets (prompted)
#   3. Installs a systemd unit (condenseit-web) that reads
#      EnvironmentFile=~/condenseit/.env
#   4. Installs the nginx vhost config
#
# After this, run:
#   ./scripts/deploy.sh
#
# Then get TLS:
#   ssh your-ssh-host 'sudo certbot --nginx -d your.domain.example'
#
# Prerequisites:
#   - SSH access configured (key-based, alias in ~/.ssh/config recommended)
#   - nginx + python3 available on the VPS (Debian/Ubuntu recommended)
#   - nginx vhost config at scripts/nginx/<your-domain>.conf
#     (copy scripts/nginx/digest.example.com.conf and replace the domain)
#
# Usage:
#   ./scripts/bootstrap-server.sh
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

info() { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
die()  { echo -e "${RED}[bootstrap] ERROR:${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve SSH target and domain
# ---------------------------------------------------------------------------
CONFIG_HOST=""
CONFIG_PATH=""
CONFIG_DIGEST_URL=""
CONFIG_DOMAIN=""
vps_from_config || die "Failed to read vps.* from config.yaml"

SSH_HOST="${DIGEST_PWA_SSH_HOST:-${CONFIG_HOST:-}}"
[[ -n "$SSH_HOST" ]] || SSH_HOST="digest-vps"

DOMAIN="${DIGEST_PWA_DOMAIN:-$CONFIG_DOMAIN}"
[[ -n "$DOMAIN" ]] || die "Cannot determine domain. Set DIGEST_PWA_DOMAIN or vps.digest_url in config.yaml."

REMOTE_DIR="${DIGEST_PWA_REMOTE_DIR:-${CONFIG_PATH:-/var/www/$DOMAIN}}"
REMOTE_DIR="${REMOTE_DIR%/}"

LIVE_URL="${DIGEST_PWA_LIVE_URL:-${CONFIG_DIGEST_URL:-https://$DOMAIN}}"
LIVE_URL="${LIVE_URL%/}"

VPS_PORT="${CONDENSEIT_VPS_PORT:-8765}"
VPS_APP_DIR="\$HOME/condenseit"
VPS_DATA_DIR="${CONDENSEIT_VPS_DATA_DIR:-\$HOME/condenseit/data}"
VPS_SERVICE="condenseit-web"

info "SSH target:  $SSH_HOST"
info "Domain:      $DOMAIN"
info "Static root: $REMOTE_DIR"
info "Service:     $VPS_SERVICE on port $VPS_PORT"

ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" true 2>/dev/null \
  || die "Cannot SSH to '$SSH_HOST'. Check DIGEST_PWA_SSH_HOST and ~/.ssh/config."

# ---------------------------------------------------------------------------
# Build and upload wheel
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

info "Uploading $WHEEL_BASENAME..."
scp -q "$WHEEL_FILE" "$SSH_HOST:/tmp/$WHEEL_BASENAME"

info "Installing on VPS..."
ssh "$SSH_HOST" WHEEL_BASENAME="$WHEEL_BASENAME" VPS_APP_DIR_REL="condenseit" bash <<'REMOTE_INSTALL'
set -euo pipefail
APP_DIR="$HOME/$VPS_APP_DIR_REL"
mkdir -p "$APP_DIR"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet --force-reinstall "/tmp/$WHEEL_BASENAME"
rm -f "/tmp/$WHEEL_BASENAME"
echo "condenseit $("$APP_DIR/.venv/bin/condenseit" --version 2>/dev/null || echo ok) installed."
REMOTE_INSTALL

# ---------------------------------------------------------------------------
# Collect secrets interactively
# ---------------------------------------------------------------------------
echo ""
echo "  Configure your VPS environment. Press Enter to accept defaults."
echo ""

read -r -p "  OpenRouter API key (sk-or-...): " VPS_OR_KEY
VPS_OR_KEY="${VPS_OR_KEY:-}"

read -r -p "  App password (empty = no auth): " VPS_AUTH_PW
VPS_AUTH_PW="${VPS_AUTH_PW:-}"

VPS_SESSION_SECRET="${DIGEST_PWA_SESSION_SECRET:-}"
if [[ -z "$VPS_SESSION_SECRET" ]]; then
  VPS_SESSION_SECRET="$(openssl rand -hex 32 2>/dev/null || LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 64)"
  echo "  Generated session secret."
fi

read -r -p "  Enable built-in scheduler? [Y/n]: " SCHED_ANSWER
SCHED_ANSWER="${SCHED_ANSWER:-Y}"
VPS_SCHEDULER_ENABLED=0
[[ "$SCHED_ANSWER" =~ ^[Yy] ]] && VPS_SCHEDULER_ENABLED=1

# ---------------------------------------------------------------------------
# Write .env on VPS (EnvironmentFile for systemd)
# ---------------------------------------------------------------------------
VPS_HOME="$(ssh "$SSH_HOST" 'echo $HOME')"
VPS_APP_DIR_REAL="$VPS_HOME/condenseit"
VPS_DATA_DIR_REAL="${VPS_DATA_DIR/\$HOME/$VPS_HOME}"

info "Writing $VPS_APP_DIR_REAL/.env on VPS..."

ssh "$SSH_HOST" "mkdir -p '$VPS_APP_DIR_REAL'"

cat <<EOF | ssh "$SSH_HOST" "cat > '$VPS_APP_DIR_REAL/.env'"
# CondenseIt VPS configuration
# Generated by scripts/bootstrap-server.sh

# LLM provider
OPENROUTER_API_KEY=$VPS_OR_KEY

# Auth
CONDENSEIT_AUTH_PASSWORD=$VPS_AUTH_PW
DIGEST_PWA_AUTH_PASSWORD=$VPS_AUTH_PW
DIGEST_PWA_SESSION_SECRET=$VPS_SESSION_SECRET

# Scheduler
CONDENSEIT_SCHEDULER_ENABLED=$VPS_SCHEDULER_ENABLED

# Data
CONDENSEIT_DATA_DIR=$VPS_DATA_DIR_REAL
CONDENSEIT_FRONTEND_DIST=

# VPS info
DIGEST_PWA_LIVE_URL=$LIVE_URL
EOF

ssh "$SSH_HOST" "chmod 600 '$VPS_APP_DIR_REAL/.env'"
info ".env written."

# ---------------------------------------------------------------------------
# Write systemd unit
# ---------------------------------------------------------------------------
VPS_REMOTE_USER="$(ssh "$SSH_HOST" 'echo $USER')"

UNIT="[Unit]
Description=CondenseIt web service
Documentation=https://github.com/wildlifechorus/condenseit
After=network.target

[Service]
Type=simple
User=$VPS_REMOTE_USER
WorkingDirectory=$VPS_APP_DIR_REAL
EnvironmentFile=$VPS_APP_DIR_REAL/.env
ExecStart=$VPS_APP_DIR_REAL/.venv/bin/uvicorn condenseit.web.app:create_app --factory --host 127.0.0.1 --port $VPS_PORT --no-access-log
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"

info "Installing systemd unit $VPS_SERVICE..."
echo "$UNIT" | ssh "$SSH_HOST" "cat > /tmp/${VPS_SERVICE}.service"
ssh "$SSH_HOST" "sudo mv /tmp/${VPS_SERVICE}.service /etc/systemd/system/${VPS_SERVICE}.service && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable $VPS_SERVICE && \
  sudo systemctl restart $VPS_SERVICE"

sleep 3
if ssh "$SSH_HOST" "sudo systemctl is-active $VPS_SERVICE" | grep -q "^active"; then
  info "$VPS_SERVICE is running."
else
  warn "$VPS_SERVICE may not be running. Check: ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -n 30'"
fi

# ---------------------------------------------------------------------------
# Install nginx vhost
# ---------------------------------------------------------------------------
NGINX_CONF_LOCAL="$ROOT/scripts/nginx/${DOMAIN}.conf"
if [[ ! -f "$NGINX_CONF_LOCAL" ]]; then
  warn "No nginx config found at $NGINX_CONF_LOCAL."
  warn "Copy scripts/nginx/digest.example.com.conf to scripts/nginx/${DOMAIN}.conf,"
  warn "replace 'digest.example.com' with '$DOMAIN', then re-run this script."
else
  info "Installing nginx config for $DOMAIN..."
  scp -q "$NGINX_CONF_LOCAL" "$SSH_HOST:/tmp/${DOMAIN}.conf"
  ssh "$SSH_HOST" \
    "sudo mv '/tmp/${DOMAIN}.conf' '/etc/nginx/sites-available/$DOMAIN' && \
     sudo ln -sf '/etc/nginx/sites-available/$DOMAIN' '/etc/nginx/sites-enabled/$DOMAIN' && \
     sudo mkdir -p '$REMOTE_DIR' && \
     sudo chown -R \"\$USER:www-data\" '$REMOTE_DIR' && \
     chmod -R g+rX '$REMOTE_DIR' && \
     sudo nginx -t && sudo systemctl reload nginx"
  info "nginx configured."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
info "Bootstrap complete."
echo ""
echo "  Next steps:"
echo ""
echo "  1. Deploy content:"
echo "       ./scripts/deploy.sh"
echo ""
echo "  2. Get a TLS certificate (DNS must point to your VPS first):"
echo "       ssh $SSH_HOST 'sudo certbot --nginx -d $DOMAIN'"
echo ""
echo "  3. Visit your digest:"
echo "       $LIVE_URL"
echo ""
echo "  Service status:  ssh $SSH_HOST 'sudo systemctl status $VPS_SERVICE'"
echo "  Service logs:    ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -f'"
