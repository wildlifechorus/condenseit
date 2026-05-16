#!/usr/bin/env bash
# =============================================================
# deploy-digest-pwa.sh - Build static digest PWA and rsync to the VPS
#
# Usage:
#   ./scripts/deploy-digest-pwa.sh              # pwa-build + rsync + nginx reload
#   ./scripts/deploy-digest-pwa.sh --skip-build # rsync + reload only
#
# SSH target and paths: set DIGEST_PWA_* env vars, or rely on vps.host,
# vps.path, and vps.digest_url in config.yaml (same as digest post-run rsync).
#
# One-time host prep: ./scripts/bootstrap-digest-pwa-server.sh
# =============================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load .env from the repo root so CONDENSEIT_* and DIGEST_PWA_* variables are
# available even when the script is called without first sourcing .env manually.
if [[ -f "$ROOT/.env" ]]; then
  set -o allexport
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +o allexport
fi

# shellcheck source=lib/pwa-vps-from-config.sh
source "$ROOT/scripts/lib/pwa-vps-from-config.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[digest-pwa]${NC} $*"; }
warn() { echo -e "${YELLOW}[digest-pwa]${NC} $*"; }
die() { echo -e "${RED}[digest-pwa] ERROR:${NC} $*" >&2; exit 1; }

SKIP_BUILD=false
for arg in "$@"; do
  case "$arg" in
    --skip-build) SKIP_BUILD=true ;;
    --help|-h)
      sed -n '3,18p' "$0" | sed 's/^# //'
      exit 0
      ;;
    *) die "Unknown option: $arg" ;;
  esac
done

# ---------------------------------------------------------------------------
# Optional ratings-service mode
#
# Set CONDENSEIT_VPS_WITH_SERVICE=1 (in .env or environment) to enable:
#   - Pull VPS ratings into local SQLite before overwriting it
#   - Stop the condenseit-web systemd service on VPS
#   - Rsync the local condenseit.db to the VPS
#   - Restart the service after the static-file rsync
#
# One-time VPS setup: run scripts/bootstrap-ratings-service.sh first.
# ---------------------------------------------------------------------------
VPS_WITH_SERVICE="${CONDENSEIT_VPS_WITH_SERVICE:-0}"
VPS_SERVICE_PORT="${CONDENSEIT_VPS_PORT:-8765}"
VPS_SERVICE="condenseit-web"
VPS_DATA_DIR="${CONDENSEIT_VPS_DATA_DIR:-\$HOME/condenseit/data}"

command -v rsync &>/dev/null || die "rsync not found"

CONDENSEIT_BIN=""
if [[ -x "$ROOT/.venv/bin/condenseit" ]]; then
  CONDENSEIT_BIN="$ROOT/.venv/bin/condenseit"
elif command -v condenseit &>/dev/null; then
  CONDENSEIT_BIN="condenseit"
else
  die "condenseit not found. Use project venv: .venv/bin/condenseit or pip install -e ."
fi

PY_BIN=""
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY_BIN="$ROOT/.venv/bin/python"
elif [[ -x "$(dirname "$CONDENSEIT_BIN")/python" ]]; then
  PY_BIN="$(dirname "$CONDENSEIT_BIN")/python"
else
  PY_BIN="$(command -v python3 || true)"
fi
[[ -n "$PY_BIN" && -x "$PY_BIN" ]] || die "python3 not found (need it to read config.yaml)"

CONFIG_HOST=""
CONFIG_PATH=""
CONFIG_DIGEST_URL=""
CONFIG_DOMAIN=""
pwa_vps_from_config || die "Failed to read vps.* from config.yaml (cd $ROOT && uv sync)"

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

LIVE_URL="${DIGEST_PWA_LIVE_URL:-}"
if [[ -z "$LIVE_URL" ]]; then
  if [[ -n "$CONFIG_DIGEST_URL" ]]; then
    LIVE_URL="$CONFIG_DIGEST_URL"
  else
    LIVE_URL="https://$DOMAIN"
  fi
fi
LIVE_URL="${LIVE_URL%/}"

info "Using $SSH_HOST:$REMOTE_DIR (smoke URL: $LIVE_URL)"

ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_HOST" true 2>/dev/null \
  || die "Cannot SSH to '$SSH_HOST'. Set DIGEST_PWA_SSH_HOST or vps.host in config.yaml, and check ~/.ssh/config."

auth_url() {
  local url="$1"
  local user="${DIGEST_PWA_BASIC_AUTH_USER:-}"
  local pass="${DIGEST_PWA_BASIC_AUTH_PASS:-}"
  if [[ -n "$user" && -n "$pass" && "$url" == https://* ]]; then
    printf '%s\n' "${url/https:\/\//https://${user}:${pass}@}"
  else
    printf '%s\n' "$url"
  fi
}

update_vps_service_package() {
  command -v uv &>/dev/null || {
    warn "uv not found; skipping remote condenseit-web package update."
    return 0
  }

  local wheel_dir
  wheel_dir="$(mktemp -d)"
  info "Building condenseit wheel for VPS service..."
  (cd "$ROOT" && uv build --wheel --out-dir "$wheel_dir" --quiet) \
    || die "uv build failed while preparing VPS service update."

  local wheel_file
  wheel_file="$(ls "$wheel_dir"/condenseit-*.whl 2>/dev/null | head -1)"
  [[ -n "$wheel_file" ]] || die "No condenseit wheel found after uv build."

  local wheel_basename
  wheel_basename="$(basename "$wheel_file")"
  info "Uploading and installing $wheel_basename on VPS..."
  scp -q "$wheel_file" "$SSH_HOST:/tmp/$wheel_basename"
  rm -rf "$wheel_dir"

  ssh "$SSH_HOST" WHEEL_BASENAME="$wheel_basename" bash <<'REMOTE_INSTALL'
set -euo pipefail
APP_DIR="$HOME/condenseit"
if [[ ! -x "$APP_DIR/.venv/bin/pip" ]]; then
  echo "Missing $APP_DIR/.venv/bin/pip; run scripts/bootstrap-ratings-service.sh first." >&2
  exit 1
fi
"$APP_DIR/.venv/bin/pip" install --quiet --force-reinstall "/tmp/$WHEEL_BASENAME"
rm -f "/tmp/$WHEEL_BASENAME"
REMOTE_INSTALL

  ssh "$SSH_HOST" "sudo systemctl restart $VPS_SERVICE" \
    || warn "$VPS_SERVICE restart failed after package update."
}

ensure_read_api_proxy() {
  [[ -n "$DOMAIN" ]] || {
    warn "DIGEST_PWA_DOMAIN/vps.domain is not set; cannot verify /api/read nginx proxy."
    return 0
  }

  local nginx_conf_path="/etc/nginx/sites-available/$DOMAIN"
  if ! ssh "$SSH_HOST" "sudo test -f '$nginx_conf_path'" >/dev/null 2>&1; then
    warn "Nginx site config not found at $nginx_conf_path; cannot patch /api/read proxy."
    return 0
  fi

  if ssh "$SSH_HOST" "sudo grep -q 'location /api/read' '$nginx_conf_path' 2>/dev/null"; then
    info "nginx already proxies /api/read."
    return 0
  fi

  info "Patching nginx to proxy /api/read to $VPS_SERVICE..."
  local block_file
  block_file="$(mktemp /tmp/condenseit_read_proxy_block_XXXXXX.txt)"
  cat > "$block_file" <<EOF
    location /api/read {
        proxy_pass         http://127.0.0.1:${VPS_SERVICE_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Host              \$host;
        proxy_set_header   X-Real-IP         \$remote_addr;
        proxy_set_header   X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto \$scheme;
    }

EOF
  scp -q "$block_file" "$SSH_HOST:/tmp/condenseit_read_proxy_block.txt"
  rm -f "$block_file"

  local patcher
  patcher="$(mktemp /tmp/condenseit_patch_read_proxy_XXXXXX.py)"
  cat > "$patcher" <<'PATCHER'
import re
import sys

conf_path = sys.argv[1]
block_path = "/tmp/condenseit_read_proxy_block.txt"

with open(block_path) as fh:
    block = fh.read()

with open(conf_path) as fh:
    conf = fh.read()

if "location /api/read" in conf:
    print("Already patched")
    raise SystemExit(0)

patched, count = re.subn(
    r"(\n    location /api/ratings\b)",
    "\n" + block + r"\1",
    conf,
    count=1,
)
if count == 0:
    patched, count = re.subn(
        r"(\n    location[ =])",
        "\n" + block + r"\1",
        conf,
        count=1,
    )
if count == 0:
    print("ERROR: Could not find insertion point in nginx config", file=sys.stderr)
    raise SystemExit(1)

with open(conf_path, "w") as fh:
    fh.write(patched)
print("Patched", conf_path)
PATCHER
  scp -q "$patcher" "$SSH_HOST:/tmp/patch_nginx_read_proxy.py"
  rm -f "$patcher"

  ssh "$SSH_HOST" \
    "sudo python3 /tmp/patch_nginx_read_proxy.py '$nginx_conf_path' && \
     rm -f /tmp/patch_nginx_read_proxy.py /tmp/condenseit_read_proxy_block.txt && \
     sudo nginx -t && sudo systemctl reload nginx" \
    || warn "Automatic /api/read nginx patch failed; add a proxy location manually."
}

# ---------------------------------------------------------------------------
# [service mode] Update remote service and pull VPS state before DB overwrite
# ---------------------------------------------------------------------------
if [[ "$VPS_WITH_SERVICE" == "1" ]]; then
  update_vps_service_package
  ensure_read_api_proxy

  EXPORT_URL="${LIVE_URL}/api/ratings/export"
  info "Pulling ratings from VPS ($EXPORT_URL) before DB sync..."
  if "$CONDENSEIT_BIN" ratings-import --url "$(auth_url "$EXPORT_URL")" 2>/dev/null; then
    info "VPS ratings merged into local SQLite."
  else
    warn "Could not pull VPS ratings (service may not be running yet). Continuing."
  fi

  READ_EXPORT_URL="${LIVE_URL}/api/read/export"
  info "Pulling read state from VPS ($READ_EXPORT_URL) before DB sync..."
  if "$CONDENSEIT_BIN" read-import --url "$(auth_url "$READ_EXPORT_URL")" 2>/dev/null; then
    info "VPS read state merged into local SQLite."
  else
    warn "Could not pull VPS read state (service may not be running yet). Continuing."
  fi
fi

if [[ "$SKIP_BUILD" == false ]]; then
  info "Building PWA bundle..."
  (cd "$ROOT" && "$CONDENSEIT_BIN" pwa-build) || die "pwa-build failed"
fi

LOCAL_SRC="$ROOT/data/pwa-dist"
[[ -d "$LOCAL_SRC" ]] || die "Missing $LOCAL_SRC (run condenseit pwa-build first)"

# ---------------------------------------------------------------------------
# [service mode] Stop VPS service before touching the SQLite file
# ---------------------------------------------------------------------------
if [[ "$VPS_WITH_SERVICE" == "1" ]]; then
  info "Stopping $VPS_SERVICE on VPS (prevents SQLite lock during rsync)..."
  ssh "$SSH_HOST" "sudo systemctl stop $VPS_SERVICE 2>/dev/null || true"
fi

info "Rsync to $SSH_HOST:$REMOTE_DIR ..."
ssh "$SSH_HOST" "sudo mkdir -p '$REMOTE_DIR' && sudo chown -R \"\$USER:www-data\" '$REMOTE_DIR' && chmod -R g+rX '$REMOTE_DIR'"
rsync -avz --delete \
  "$LOCAL_SRC/" \
  "$SSH_HOST:$REMOTE_DIR/"

# ---------------------------------------------------------------------------
# [service mode] Rsync SQLite DB so the VPS shows the latest digest articles
# ---------------------------------------------------------------------------
if [[ "$VPS_WITH_SERVICE" == "1" ]]; then
  LOCAL_DB="$ROOT/data/condenseit.db"
  if [[ -f "$LOCAL_DB" ]]; then
    info "Syncing SQLite DB to VPS ($SSH_HOST:$VPS_DATA_DIR/condenseit.db)..."
    ssh "$SSH_HOST" "mkdir -p '$VPS_DATA_DIR'"
    rsync -avz "$LOCAL_DB" "$SSH_HOST:$VPS_DATA_DIR/condenseit.db"
  else
    warn "Local DB not found at $LOCAL_DB; skipping DB rsync."
  fi
fi

info "Reloading nginx (if present)..."
if ssh "$SSH_HOST" "command -v nginx >/dev/null 2>&1"; then
  ssh "$SSH_HOST" "sudo nginx -t && sudo systemctl reload nginx" \
    || warn "nginx reload failed; check sudoers or run manually on the host."
else
  warn "nginx not found on remote; skipped reload."
fi

# ---------------------------------------------------------------------------
# [service mode] Restart the condenseit-web service after all files are in place
# ---------------------------------------------------------------------------
if [[ "$VPS_WITH_SERVICE" == "1" ]]; then
  info "Starting $VPS_SERVICE on VPS..."
  if ssh "$SSH_HOST" "sudo systemctl start $VPS_SERVICE"; then
    info "$VPS_SERVICE started."
  else
    warn "$VPS_SERVICE failed to start. Run: ssh $SSH_HOST 'journalctl -u $VPS_SERVICE -n 50'"
  fi
fi

info "Smoke check..."
# Build a smoke URL that includes basic auth credentials when configured so the
# check doesn't spuriously 401 on password-protected deployments.
SMOKE_URL="$LIVE_URL/"
_AUTH_USER="${DIGEST_PWA_BASIC_AUTH_USER:-}"
_AUTH_PASS="${DIGEST_PWA_BASIC_AUTH_PASS:-}"
if [[ -n "$_AUTH_USER" && -n "$_AUTH_PASS" ]]; then
  # Inject credentials into the URL: https://user:pass@host/path
  SMOKE_URL="${LIVE_URL/https:\/\//https://${_AUTH_USER}:${_AUTH_PASS}@}/"
fi
code=$(curl -sL -o /dev/null -w '%{http_code}' "$SMOKE_URL" || echo "000")
if [[ "$code" == "200" ]]; then
  info "HTTP $code for $LIVE_URL"
else
  warn "HTTP $code for $LIVE_URL (TLS or first deploy may still be in progress)"
fi

echo ""
info "Done. Public URL: $LIVE_URL"
if [[ "$VPS_WITH_SERVICE" == "1" ]]; then
  info "Rate articles on the digest cards: $LIVE_URL/"
  info "Ratings export:   $LIVE_URL/api/ratings/export"
  info "Read export:      $LIVE_URL/api/read/export"
  info "Set in .env:      CONDENSEIT_RATINGS_IMPORT_URL=$LIVE_URL/api/ratings/export"
  info "Set in .env:      CONDENSEIT_READ_IMPORT_URL=$LIVE_URL/api/read/export"
fi
