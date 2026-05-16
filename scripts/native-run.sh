#!/usr/bin/env bash
# Full digest with native Ollama (Metal on Apple Silicon).
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv
log "Running digest with native Ollama"
condenseit run "$@"
