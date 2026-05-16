#!/usr/bin/env bash
# One-time VPS prep for digest hosting (run on the server).
set -euo pipefail
DEPLOY_PATH="${1:-/var/www/condenseit}"
sudo mkdir -p "$DEPLOY_PATH"
sudo chown -R "$USER:$USER" "$DEPLOY_PATH"
echo "Ready: $DEPLOY_PATH"
