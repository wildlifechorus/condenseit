#!/usr/bin/env bash
# Docker web UI (:8899) plus native digest on the host (Ollama, not in Docker).
#
# Usage:
#   ./scripts/docker-ui-digest.sh              # compose up --build, condenseit run
#   ./scripts/docker-ui-digest.sh --dry-run    # flags pass through to condenseit run
#   ./scripts/docker-ui-digest.sh run --dry-run
#   ./scripts/docker-ui-digest.sh ui           # (re)start UI only, no digest
#   ./scripts/docker-ui-digest.sh restart      # compose down + up --build, no digest
#
# Requires Docker. For UI-only or digest-only, use make docker-up / make run instead.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

ensure_config
mkdir -p data/digests

case "${1:-}" in
  ui)
    exec "$SCRIPT_DIR/docker-up.sh"
    ;;
  restart)
    shift || true
    "$SCRIPT_DIR/docker-down.sh"
    exec "$SCRIPT_DIR/docker-up.sh"
    ;;
  *)
    [[ "${1:-}" == "run" ]] && shift || true
    exec "$SCRIPT_DIR/run-with-ollama.sh" "$@"
    ;;
esac
