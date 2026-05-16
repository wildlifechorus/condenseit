#!/usr/bin/env bash
# Start web UI + admin panel locally.
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv
PORT="${PORT:-8899}"
log "Serving on http://127.0.0.1:${PORT}/"
condenseit serve --port "$PORT" "$@"
