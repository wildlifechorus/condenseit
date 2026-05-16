#!/usr/bin/env bash
# =============================================================
# bootstrap-digest-pwa-server.sh - One-time nginx vhost on your VPS
#
# Run from your laptop (uses SSH). After this, obtain TLS with:
#   ssh your-ssh-host 'sudo certbot --nginx -d your.domain.example'
#
# Usage:
#   ./scripts/bootstrap-digest-pwa-server.sh
# =============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/pwa-vps-from-config.sh
source "$ROOT/scripts/lib/pwa-vps-from-config.sh"

die() { echo "ERROR: $*" >&2; exit 1; }

PY_BIN=""
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY_BIN="$ROOT/.venv/bin/python"
else
  PY_BIN="$(command -v python3 || true)"
fi
[[ -n "$PY_BIN" && -x "$PY_BIN" ]] || die "python3 not found (need .venv: uv sync)"

CONFIG_HOST=""
CONFIG_PATH=""
CONFIG_DIGEST_URL=""
CONFIG_DOMAIN=""
pwa_vps_from_config || die "Failed to read vps.* from config.yaml"

SSH_HOST="${DIGEST_PWA_SSH_HOST:-${CONFIG_HOST:-}}"
if [[ -z "$SSH_HOST" ]]; then
  SSH_HOST="digest-vps"
fi

DOMAIN="${DIGEST_PWA_DOMAIN:-$CONFIG_DOMAIN}"

REMOTE_DIR="${DIGEST_PWA_REMOTE_DIR:-}"
if [[ -z "$REMOTE_DIR" ]]; then
  if [[ -n "$CONFIG_PATH" ]]; then
    REMOTE_DIR="$CONFIG_PATH"
  else
    REMOTE_DIR="/var/www/$DOMAIN"
  fi
fi
REMOTE_DIR="${REMOTE_DIR%/}"

CONF_LOCAL="$ROOT/scripts/nginx/${DOMAIN}.conf"
CONF_REMOTE="/tmp/${DOMAIN}.conf"

[[ -f "$CONF_LOCAL" ]] || die "Missing nginx template: $CONF_LOCAL (copy digest.example.com.conf for your domain)"

ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" true \
  || die "Cannot SSH to $SSH_HOST (set DIGEST_PWA_SSH_HOST or vps.host in config.yaml)"

echo "Creating $REMOTE_DIR on $SSH_HOST ..."
ssh "$SSH_HOST" "sudo mkdir -p '$REMOTE_DIR' && sudo chown -R \"\$USER:www-data\" '$REMOTE_DIR' && chmod -R g+rX '$REMOTE_DIR'"

echo "Installing nginx site for $DOMAIN ..."
scp "$CONF_LOCAL" "$SSH_HOST:$CONF_REMOTE"
ssh "$SSH_HOST" "sudo mv '$CONF_REMOTE' /etc/nginx/sites-available/$DOMAIN && \
  sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN && \
  sudo nginx -t && sudo systemctl reload nginx"

echo ""
echo "Next: issue a certificate (DNS must already point here):"
echo "  ssh $SSH_HOST 'sudo certbot --nginx -d $DOMAIN'"
echo ""
echo "Then deploy content:"
echo "  ./scripts/deploy-digest-pwa.sh"
