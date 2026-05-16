#!/usr/bin/env bash
# =============================================================
# bootstrap-ratings-service.sh - One-time VPS setup for server-side ratings
#
# This script runs from your LOCAL machine over SSH and:
#   1. Creates a Python venv on the VPS and installs condenseit
#   2. Writes a systemd unit (condenseit-web) that runs the FastAPI
#      ratings server on 127.0.0.1:8765
#   3. Patches the nginx site config to proxy /rate and /api/ratings
#      to the FastAPI process, then reloads nginx
#
# After this you can:
#   - Visit https://your-domain/rate to rate articles server-side
#   - Set CONDENSEIT_RATINGS_IMPORT_URL=https://your-domain/api/ratings/export
#     in your .env so each local digest run pulls remote ratings automatically
#   - Set CONDENSEIT_VPS_WITH_SERVICE=1 so deploy-digest-pwa.sh syncs the
#     SQLite DB and manages the service on every deploy
#
# Prerequisites:
#   - SSH access already configured (same as deploy-digest-pwa.sh)
#   - bootstrap-digest-pwa-server.sh already run (nginx vhost exists)
#   - python3 + pip available on VPS (most Debian/Ubuntu VPS have them)
#
# Usage:
#   ./scripts/bootstrap-ratings-service.sh
# =============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=lib/pwa-vps-from-config.sh
source "$ROOT/scripts/lib/pwa-vps-from-config.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[ratings-bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[ratings-bootstrap]${NC} $*"; }
die()  { echo -e "${RED}[ratings-bootstrap] ERROR:${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Resolve Python binary (needs to read config.yaml)
# ---------------------------------------------------------------------------
PY_BIN=""
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY_BIN="$ROOT/.venv/bin/python"
else
  PY_BIN="$(command -v python3 || true)"
fi
[[ -n "$PY_BIN" && -x "$PY_BIN" ]] || die "python3 not found (run: uv sync in the repo)"

# ---------------------------------------------------------------------------
# Resolve SSH / domain from config or env
# ---------------------------------------------------------------------------
CONFIG_HOST=""
CONFIG_PATH=""
CONFIG_DIGEST_URL=""
CONFIG_DOMAIN=""
pwa_vps_from_config || die "Failed to read vps.* from config.yaml"

SSH_HOST="${DIGEST_PWA_SSH_HOST:-${CONFIG_HOST:-}}"
[[ -n "$SSH_HOST" ]] || SSH_HOST="digest-vps"

DOMAIN="${DIGEST_PWA_DOMAIN:-$CONFIG_DOMAIN}"
[[ -n "$DOMAIN" ]] || die "Cannot determine domain. Set DIGEST_PWA_DOMAIN or vps.digest_url in config.yaml."

REMOTE_DIR="${DIGEST_PWA_REMOTE_DIR:-}"
if [[ -z "$REMOTE_DIR" ]]; then
  REMOTE_DIR="${CONFIG_PATH:-/var/www/$DOMAIN}"
fi
REMOTE_DIR="${REMOTE_DIR%/}"

LIVE_URL="${DIGEST_PWA_LIVE_URL:-${CONFIG_DIGEST_URL:-https://$DOMAIN}}"
LIVE_URL="${LIVE_URL%/}"

# Service-specific settings
VPS_PORT="${CONDENSEIT_VPS_PORT:-8765}"
VPS_APP_DIR="${CONDENSEIT_VPS_APP_DIR:-\$HOME/condenseit}"
VPS_DATA_DIR="${CONDENSEIT_VPS_DATA_DIR:-\$HOME/condenseit/data}"
VPS_SERVICE="condenseit-web"

info "SSH target: $SSH_HOST"
info "Domain:     $DOMAIN"
info "Service:    $VPS_SERVICE on port $VPS_PORT"

# ---------------------------------------------------------------------------
# Check SSH connectivity
# ---------------------------------------------------------------------------
ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" true 2>/dev/null \
  || die "Cannot SSH to '$SSH_HOST'. Check DIGEST_PWA_SSH_HOST and ~/.ssh/config."

# ---------------------------------------------------------------------------
# Build a wheel from the local source and upload it to the VPS
# ---------------------------------------------------------------------------
WHEEL_DIR="$(mktemp -d)"
trap 'rm -rf "$WHEEL_DIR"' EXIT

info "Building condenseit wheel..."
(cd "$ROOT" && uv build --wheel --out-dir "$WHEEL_DIR" --quiet) \
  || die "uv build failed. Is 'uv' installed? (brew install uv)"

WHEEL_FILE="$(ls "$WHEEL_DIR"/condenseit-*.whl 2>/dev/null | head -1)"
[[ -n "$WHEEL_FILE" ]] || die "No wheel found after uv build."
info "Built: $(basename "$WHEEL_FILE")"

WHEEL_BASENAME="$(basename "$WHEEL_FILE")"
info "Uploading wheel to VPS..."
# Keep the original filename - pip requires a valid wheel name to install from path.
scp -q "$WHEEL_FILE" "$SSH_HOST:/tmp/$WHEEL_BASENAME"

# ---------------------------------------------------------------------------
# Install condenseit on VPS
# ---------------------------------------------------------------------------
info "Installing condenseit on VPS (creating venv at ~/condenseit/.venv)..."
ssh "$SSH_HOST" WHEEL_BASENAME="$WHEEL_BASENAME" bash <<'REMOTE_INSTALL'
set -euo pipefail
APP_DIR="$HOME/condenseit"
DATA_DIR="$APP_DIR/data"
mkdir -p "$APP_DIR" "$DATA_DIR"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet --force-reinstall "/tmp/$WHEEL_BASENAME"
rm -f "/tmp/$WHEEL_BASENAME"

echo "condenseit installed: $("$APP_DIR/.venv/bin/condenseit" --version 2>/dev/null || echo 'ok')"
REMOTE_INSTALL

# ---------------------------------------------------------------------------
# Write and install the systemd service unit
# ---------------------------------------------------------------------------
info "Installing systemd unit: $VPS_SERVICE..."

VPS_REMOTE_USER="$(ssh "$SSH_HOST" 'echo $USER')"
VPS_HOME="$(ssh "$SSH_HOST" 'echo $HOME')"
VPS_APP_DIR_REAL="${VPS_APP_DIR/\$HOME/$VPS_HOME}"
VPS_DATA_DIR_REAL="${VPS_DATA_DIR/\$HOME/$VPS_HOME}"

UNIT_CONTENT="[Unit]
Description=CondenseIt web service (ratings API)
Documentation=https://github.com/condenseit/condenseit
After=network.target

[Service]
Type=simple
User=$VPS_REMOTE_USER
WorkingDirectory=$VPS_APP_DIR_REAL
Environment=CONDENSEIT_DATA_DIR=$VPS_DATA_DIR_REAL
Environment=CONDENSEIT_FRONTEND_DIST=
ExecStart=$VPS_APP_DIR_REAL/.venv/bin/uvicorn condenseit.web.app:create_app --factory --host 127.0.0.1 --port $VPS_PORT --no-access-log
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"

ssh "$SSH_HOST" "cat > /tmp/${VPS_SERVICE}.service" <<EOF
$UNIT_CONTENT
EOF

ssh "$SSH_HOST" "sudo mv /tmp/${VPS_SERVICE}.service /etc/systemd/system/${VPS_SERVICE}.service && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable $VPS_SERVICE && \
  sudo systemctl restart $VPS_SERVICE"

info "Waiting for service to start..."
sleep 3
if ssh "$SSH_HOST" "sudo systemctl is-active $VPS_SERVICE" | grep -q "^active"; then
  info "$VPS_SERVICE is running."
else
  warn "$VPS_SERVICE may not be running yet. Check: ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -n 30'"
fi

# ---------------------------------------------------------------------------
# Patch nginx conf to add proxy locations for /rate and /api/ratings
#
# Write the Python patch script to a local temp file first, then scp it to
# the VPS. This avoids bash variable-expansion issues when embedding nginx
# location blocks (which contain $host, $remote_addr, etc.) inside heredocs.
# ---------------------------------------------------------------------------
info "Checking nginx site config for $DOMAIN..."
NGINX_CONF_PATH="/etc/nginx/sites-available/$DOMAIN"

# Build the proxy block text (nginx vars must appear literally in the conf,
# so we use single-quoted strings in Python to prevent any shell expansion).
PROXY_BLOCK_TEXT="
    # CondenseIt ratings API + rate page (added by bootstrap-ratings-service.sh)
    location = /rate {
        proxy_pass         http://127.0.0.1:${VPS_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

    location /api/ratings {
        proxy_pass         http://127.0.0.1:${VPS_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

    location /api/read {
        proxy_pass         http://127.0.0.1:${VPS_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        proxy_pass         http://127.0.0.1:${VPS_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }
"

# Only patch if the proxy locations are not already in the conf
if ssh "$SSH_HOST" "sudo grep -q 'location /api/ratings' '$NGINX_CONF_PATH' 2>/dev/null"; then
  info "nginx conf already has proxy locations; skipping patch."
else
  if ssh "$SSH_HOST" "sudo test -f '$NGINX_CONF_PATH'"; then
    info "Patching $NGINX_CONF_PATH with proxy locations..."

    # Write the proxy block to a local temp file (avoids ALL quoting issues -
    # the block contains nginx $host/$remote_addr vars that must not expand).
    LOCAL_BLOCK_FILE="$(mktemp /tmp/condenseit_proxy_block_XXXXXX.txt)"
    printf '%s' "$PROXY_BLOCK_TEXT" > "$LOCAL_BLOCK_FILE"
    scp -q "$LOCAL_BLOCK_FILE" "$SSH_HOST:/tmp/condenseit_proxy_block.txt"
    rm -f "$LOCAL_BLOCK_FILE"

    # Write the patcher to a local temp file then scp it; no shell expansion
    # of nginx vars since the script reads the block from a separate file.
    LOCAL_PATCHER="$(mktemp /tmp/condenseit_patch_nginx_XXXXXX.py)"
    cat > "$LOCAL_PATCHER" <<'PATCHER'
import re, sys

conf_path = sys.argv[1]
block_path = "/tmp/condenseit_proxy_block.txt"

with open(block_path) as fh:
    block = fh.read()

with open(conf_path) as fh:
    conf = fh.read()

if block.strip() in conf:
    print("Already patched, nothing to do.")
    sys.exit(0)

# Insert before the first static-file comment or bare location block.
patched, n = re.subn(
    r"(\n    # (?:Static|PWA|-{3,}))",
    "\n" + block + r"\1",
    conf,
    count=1,
)
if n == 0:
    patched, n = re.subn(
        r"(\n    location[ =])",
        "\n" + block + r"\1",
        conf,
        count=1,
    )
if n == 0:
    print("ERROR: Could not find insertion point in", conf_path, file=sys.stderr)
    sys.exit(1)

with open(conf_path, "w") as fh:
    fh.write(patched)
print("Patched", conf_path)
PATCHER
    scp -q "$LOCAL_PATCHER" "$SSH_HOST:/tmp/patch_nginx_condenseit.py"
    rm -f "$LOCAL_PATCHER"

    ssh "$SSH_HOST" \
      "sudo python3 /tmp/patch_nginx_condenseit.py '$NGINX_CONF_PATH' && \
       rm -f /tmp/patch_nginx_condenseit.py /tmp/condenseit_proxy_block.txt" \
      || {
        warn "Automatic nginx patch failed. Add these locations manually to $NGINX_CONF_PATH:"
        echo "$PROXY_BLOCK_TEXT"
      }
  else
    warn "Nginx site config not found at $NGINX_CONF_PATH."
    warn "Run bootstrap-digest-pwa-server.sh first, or add proxy locations manually."
    warn "Required nginx locations:"
    echo "$PROXY_BLOCK_TEXT"
  fi
fi

# Reload nginx
if ssh "$SSH_HOST" "command -v nginx >/dev/null 2>&1"; then
  info "Testing and reloading nginx..."
  ssh "$SSH_HOST" "sudo nginx -t && sudo systemctl reload nginx" \
    || warn "nginx reload failed. Check the config on the server."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
info "Bootstrap complete."
echo ""
echo "  Rate page:        $LIVE_URL/rate"
echo "  Ratings export:   $LIVE_URL/api/ratings/export"
echo "  Service status:   ssh $SSH_HOST 'sudo systemctl status $VPS_SERVICE'"
echo "  Service logs:     ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -f'"
echo ""
echo "Add to your .env:"
echo "  CONDENSEIT_RATINGS_IMPORT_URL=$LIVE_URL/api/ratings/export"
echo "  CONDENSEIT_VPS_WITH_SERVICE=1"
echo ""
echo "Then run:"
echo "  ./scripts/deploy-digest-pwa.sh   # syncs SQLite DB + restarts service"
