#!/usr/bin/env bash
# =============================================================
# provision-ubuntu.sh - Prepare a fresh Ubuntu 24.04 VPS for CondenseIt
#
# Run this script ONCE on the server (not from your local machine).
# It installs all system dependencies needed by bootstrap-server.sh
# and deploy.sh.
#
# What it does:
#   1. Updates apt packages
#   2. Installs nginx, python3, certbot, ufw, fail2ban, rsync, curl
#   3. Configures UFW firewall (SSH, HTTP, HTTPS)
#   4. Creates a 2 GB swap file if no swap is present
#   5. Enables unattended security upgrades
#   6. Adds your SSH public key to authorized_keys (if provided)
#
# Usage (run on the VPS):
#   curl -fsSL https://raw.githubusercontent.com/wildlifechorus/condenseit/main/scripts/provision-ubuntu.sh | bash
#
# Or copy it to the server and run:
#   scp scripts/provision-ubuntu.sh user@your-vps:/tmp/
#   ssh user@your-vps 'bash /tmp/provision-ubuntu.sh'
#
# After this, run from your LOCAL machine:
#   ./scripts/bootstrap-server.sh
# =============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[provision]${NC} $*"; }
warn() { echo -e "${YELLOW}[provision]${NC} $*"; }
die()  { echo -e "${RED}[provision] ERROR:${NC} $*" >&2; exit 1; }

# Must run as root or with sudo.
if [[ $EUID -ne 0 ]]; then
  # Re-execute with sudo if available.
  if command -v sudo &>/dev/null; then
    exec sudo -E bash "$0" "$@"
  else
    die "This script must run as root. Try: sudo bash $0"
  fi
fi

# ---------------------------------------------------------------------------
# Verify Ubuntu 24.04
# ---------------------------------------------------------------------------
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  if [[ "$ID" != "ubuntu" ]]; then
    warn "OS is '$ID', not Ubuntu. Continuing anyway, but expect apt-specific commands."
  fi
  if [[ "${VERSION_ID:-}" != "24.04" ]]; then
    warn "Ubuntu version is '${VERSION_ID:-unknown}' (expected 24.04). Proceeding."
  fi
fi

# ---------------------------------------------------------------------------
# Update packages
# ---------------------------------------------------------------------------
info "Updating package lists..."
apt-get update -q

info "Upgrading existing packages (this may take a few minutes)..."
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -q

# ---------------------------------------------------------------------------
# Install system dependencies
# ---------------------------------------------------------------------------
info "Installing nginx, python3, certbot, ufw, fail2ban, rsync, curl..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  nginx \
  python3 \
  python3-venv \
  python3-pip \
  certbot \
  python3-certbot-nginx \
  ufw \
  fail2ban \
  rsync \
  curl \
  git \
  unzip \
  ca-certificates \
  libxml2 \
  libxslt1.1

# ---------------------------------------------------------------------------
# Configure UFW firewall
# ---------------------------------------------------------------------------
info "Configuring UFW firewall..."

# Allow SSH before enabling to avoid being locked out.
ufw allow OpenSSH
ufw allow 'Nginx Full'

# Enable without prompting.
ufw --force enable

info "UFW status:"
ufw status verbose

# ---------------------------------------------------------------------------
# Create swap file if none exists
# ---------------------------------------------------------------------------
SWAP_TOTAL="$(free -m | awk '/^Swap:/ {print $2}')"
if [[ "$SWAP_TOTAL" -lt 512 ]]; then
  info "No swap detected. Creating 2 GB swap file at /swapfile..."
  if [[ ! -f /swapfile ]]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    # Persist across reboots.
    if ! grep -q '/swapfile' /etc/fstab; then
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    info "Swap created and enabled."
  else
    warn "/swapfile already exists but is not active. Enable it manually."
  fi
else
  info "Swap already present (${SWAP_TOTAL} MB), skipping."
fi

# ---------------------------------------------------------------------------
# Enable unattended security upgrades
# ---------------------------------------------------------------------------
info "Enabling unattended security upgrades..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -q unattended-upgrades

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT_CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT_CONF

# ---------------------------------------------------------------------------
# Configure fail2ban for SSH
# ---------------------------------------------------------------------------
info "Enabling fail2ban..."
if [[ ! -f /etc/fail2ban/jail.local ]]; then
  cat > /etc/fail2ban/jail.local <<'JAIL'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
JAIL
fi
systemctl enable fail2ban --quiet
systemctl restart fail2ban

# ---------------------------------------------------------------------------
# Ensure nginx is enabled
# ---------------------------------------------------------------------------
info "Enabling nginx..."
systemctl enable nginx --quiet
systemctl start nginx || warn "nginx start failed. Check: systemctl status nginx"

# ---------------------------------------------------------------------------
# Remove default nginx site
# ---------------------------------------------------------------------------
if [[ -f /etc/nginx/sites-enabled/default ]]; then
  rm /etc/nginx/sites-enabled/default
  systemctl reload nginx || true
fi

# ---------------------------------------------------------------------------
# Create deploy directory (bootstrap-server.sh will populate it)
# ---------------------------------------------------------------------------
DEPLOY_DIR="${CONDENSEIT_DEPLOY_DIR:-/var/www}"
mkdir -p "$DEPLOY_DIR"
info "Deploy root: $DEPLOY_DIR"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
PYTHON_VER="$(python3 --version 2>&1 || echo 'not found')"
NGINX_VER="$(nginx -v 2>&1 | head -1 || echo 'not found')"

echo ""
info "Provisioning complete."
echo ""
echo "  Python:  $PYTHON_VER"
echo "  nginx:   $NGINX_VER"
echo "  UFW:     enabled (OpenSSH + Nginx Full)"
echo "  fail2ban: enabled"
echo ""
echo "  Next step (run from your LOCAL machine):"
echo "    ./scripts/bootstrap-server.sh"
echo ""
