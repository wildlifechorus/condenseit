#!/usr/bin/env bash
# Dry run - collect and rank feeds only, no LLM summarization.
# Useful for testing sources and config without waiting for Ollama.
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv
log "Dry run (no LLM)"
condenseit run --dry-run "$@"
