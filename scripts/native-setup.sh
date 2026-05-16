#!/usr/bin/env bash
# One-time local setup: Python venv, Ollama model, frontend build.
#
# Usage:
#   ./scripts/native-setup.sh
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv

if command -v ollama >/dev/null 2>&1; then
  MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
  log "Pulling Ollama model: $MODEL"
  ollama pull "$MODEL"
else
  log "Ollama not found - skipping model pull."
  log "Install Ollama: https://ollama.com/download"
  log "Or use OpenRouter: set llm.provider: openrouter in config.yaml"
fi

ensure_frontend

log "Setup complete."
log ""
log "  Start web UI:   ./scripts/native-serve.sh"
log "  Run digest:     condenseit run"
log "  Dry run:        ./scripts/run-without-ollama.sh"
