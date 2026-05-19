#!/usr/bin/env bash
# =============================================================
# bootstrap-server.sh - One-time VPS setup for a CondenseIt instance
#
# Runs from your LOCAL machine over SSH and:
#   1. Creates <app_dir>/.venv and installs condenseit
#   2. Creates <app_dir>/.env with your secrets (prompted)
#   3. Installs a systemd unit that reads EnvironmentFile=<app_dir>/.env
#   4. Installs the nginx vhost config
#
# After this, run:
#   ./scripts/deploy.sh --instance <name>
#
# Usage:
#   ./scripts/bootstrap-server.sh                    # interactive instance picker
#   ./scripts/bootstrap-server.sh --instance main    # bootstrap a specific instance
#   ./scripts/bootstrap-server.sh --instance inbardo
#
# Instances are defined in config.yaml under instances:.
#
# Prerequisites:
#   - SSH access configured (key-based, alias in ~/.ssh/config recommended)
#   - nginx + python3 available on the VPS (Debian/Ubuntu recommended)
#   - nginx vhost config at scripts/nginx/<domain>.conf
#     (copy scripts/nginx/digest.example.com.conf and replace the domain)
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

INSTANCE_NAME=""

# Parse --instance <name>.
args=("$@")
for i in "${!args[@]}"; do
  case "${args[$i]}" in
    --instance)
      next=$((i + 1))
      [[ $next -lt ${#args[@]} ]] || die "--instance requires a value"
      INSTANCE_NAME="${args[$next]}"
      ;;
    --help|-h)
      sed -n '3,26p' "$0" | sed 's/^# //'
      exit 0
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Instance picker
# ---------------------------------------------------------------------------
INSTANCE_LINES=()
while IFS= read -r _line; do
  [[ -n "$_line" ]] && INSTANCE_LINES+=("$_line")
done < <(vps_list_instances 2>/dev/null || true)

if [[ ${#INSTANCE_LINES[@]} -eq 0 ]]; then
  INSTANCE_NAME="default"
elif [[ ${#INSTANCE_LINES[@]} -eq 1 && -z "$INSTANCE_NAME" ]]; then
  INSTANCE_NAME="${INSTANCE_LINES[0]%%|*}"
  info "Auto-selected instance: $INSTANCE_NAME"
elif [[ -z "$INSTANCE_NAME" ]]; then
  echo ""
  echo "  Select instance to bootstrap:"
  for i in "${!INSTANCE_LINES[@]}"; do
    name="${INSTANCE_LINES[$i]%%|*}"
    label="${INSTANCE_LINES[$i]#*|}"
    printf "  %d) %-16s %s\n" "$((i+1))" "$name" "$label"
  done
  echo ""
  read -r -p "  Enter number [1]: " PICK
  PICK="${PICK:-1}"
  if ! [[ "$PICK" =~ ^[0-9]+$ ]] || (( PICK < 1 || PICK > ${#INSTANCE_LINES[@]} )); then
    die "Invalid selection: $PICK"
  fi
  INSTANCE_NAME="${INSTANCE_LINES[$((PICK-1))]%%|*}"
fi

# ---------------------------------------------------------------------------
# Resolve settings for the selected instance
# ---------------------------------------------------------------------------
CONFIG_HOST=""
CONFIG_PATH=""
CONFIG_DIGEST_URL=""
CONFIG_DOMAIN=""
CONFIG_PORT=""
CONFIG_APP_DIR=""
CONFIG_SERVICE=""
CONFIG_LABEL=""

vps_from_config_instance "$INSTANCE_NAME" \
  || die "Failed to read instance '$INSTANCE_NAME' from config.yaml"

if [[ "$INSTANCE_NAME" == "default" ]]; then
  vps_from_config || die "Failed to read vps.* from config.yaml"
fi

# For named instances use instance config directly; env vars are for the
# "default" (legacy single-instance) path only, so they don't bleed into
# unrelated instances.
if [[ "$INSTANCE_NAME" == "default" ]]; then
  SSH_HOST="${DIGEST_PWA_SSH_HOST:-${CONFIG_HOST:-}}"
  [[ -n "$SSH_HOST" ]] || SSH_HOST="digest-vps"
  DOMAIN="${DIGEST_PWA_DOMAIN:-${CONFIG_DOMAIN:-}}"
  REMOTE_DIR="${DIGEST_PWA_REMOTE_DIR:-${CONFIG_PATH:-/var/www/${DOMAIN:-condenseit}}}"
  LIVE_URL="${DIGEST_PWA_LIVE_URL:-${CONFIG_DIGEST_URL:-https://${DOMAIN:-localhost}}}"
else
  SSH_HOST="${CONFIG_HOST:-}"
  [[ -n "$SSH_HOST" ]] || SSH_HOST="digest-vps"
  DOMAIN="${CONFIG_DOMAIN:-}"
  REMOTE_DIR="${CONFIG_PATH:-/var/www/${DOMAIN:-condenseit}}"
  LIVE_URL="${CONFIG_DIGEST_URL:-https://${DOMAIN:-localhost}}"
fi

REMOTE_DIR="${REMOTE_DIR%/}"
LIVE_URL="${LIVE_URL%/}"

[[ -n "$DOMAIN" ]] || die "Cannot determine domain. Configure instances: in config.yaml."

VPS_PORT="${CONFIG_PORT:-${CONDENSEIT_VPS_PORT:-8765}}"
VPS_SERVICE="${CONFIG_SERVICE:-condenseit-web}"
VPS_APP_DIR_TEMPLATE="${CONFIG_APP_DIR:-~/condenseit}"
VPS_DATA_DIR="${CONDENSEIT_VPS_DATA_DIR:-${VPS_APP_DIR_TEMPLATE}/data}"

info "Instance:    ${CONFIG_LABEL:-$INSTANCE_NAME}"
info "SSH target:  $SSH_HOST"
info "Domain:      $DOMAIN"
info "Static root: $REMOTE_DIR"
info "Service:     $VPS_SERVICE on port $VPS_PORT"
info "App dir:     $VPS_APP_DIR_TEMPLATE"

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
ssh "$SSH_HOST" WHEEL_BASENAME="$WHEEL_BASENAME" VPS_APP_DIR="$VPS_APP_DIR_TEMPLATE" bash <<'REMOTE_INSTALL'
set -euo pipefail
APP_DIR="${VPS_APP_DIR/#\~/$HOME}"
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
echo "  Configure the '$INSTANCE_NAME' VPS environment. Press Enter to accept defaults."
echo ""

read -r -p "  OpenRouter API key (sk-or-...) [leave blank for Ollama]: " VPS_OR_KEY
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
VPS_APP_DIR_REAL="${VPS_APP_DIR_TEMPLATE/#\~/$VPS_HOME}"
VPS_DATA_DIR_REAL="${VPS_DATA_DIR/#\~/$VPS_HOME}"
VPS_DATA_DIR_REAL="${VPS_DATA_DIR_REAL/\$HOME/$VPS_HOME}"

info "Writing $VPS_APP_DIR_REAL/.env on VPS..."

ssh "$SSH_HOST" "mkdir -p '$VPS_APP_DIR_REAL'"

cat <<EOF | ssh "$SSH_HOST" "cat > '$VPS_APP_DIR_REAL/.env'"
# CondenseIt VPS configuration - instance: $INSTANCE_NAME
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
Description=CondenseIt web service ($INSTANCE_NAME)
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
  warn "replace 'digest.example.com' with '$DOMAIN' and the proxy port with '$VPS_PORT',"
  warn "then re-run this script."
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
info "Bootstrap complete for instance '$INSTANCE_NAME'."
echo ""
echo "  Next steps:"
echo ""
echo "  1. Deploy content:"
echo "       ./scripts/deploy.sh --instance $INSTANCE_NAME"
echo ""
echo "  2. Visit your digest:"
echo "       $LIVE_URL"
echo ""
echo "  Service status:  ssh $SSH_HOST 'sudo systemctl status $VPS_SERVICE'"
echo "  Service logs:    ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -f'"
