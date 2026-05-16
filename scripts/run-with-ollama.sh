#!/usr/bin/env bash
# Full digest on the host with local Ollama (Metal on Apple Silicon).
#
# Usage:
#   ./scripts/run-with-ollama.sh          # run digest once
#   ./scripts/run-with-ollama.sh --serve  # start web UI instead of running digest
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv

if [[ "${1:-}" == "--serve" ]]; then
  shift
  log "Starting web UI at http://127.0.0.1:${PORT:-8899}/"
  condenseit serve --port "${PORT:-8899}" "$@"
else
  log "Running digest with Ollama"
  condenseit run "$@"
fi
