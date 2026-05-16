#!/usr/bin/env bash
# Start the web UI and admin panel locally (no Docker).
#
# Builds the frontend automatically on first run if frontend/dist is missing.
#
# Usage:
#   ./scripts/native-serve.sh
#   PORT=8080 ./scripts/native-serve.sh
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv
ensure_frontend
PORT="${PORT:-8899}"
log "Serving on http://127.0.0.1:${PORT}/"
condenseit serve --port "$PORT" "$@"
