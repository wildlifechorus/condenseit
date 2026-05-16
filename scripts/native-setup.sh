#!/usr/bin/env bash
# Install Python deps and pull Ollama model (native macOS/Linux).
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv

if command -v ollama >/dev/null 2>&1; then
  MODEL="${OLLAMA_MODEL:-llama3.2:3b}"
  log "Pulling Ollama model: $MODEL"
  ollama pull "$MODEL"
else
  log "Ollama not installed. Install: https://ollama.com/download"
  log "Or use Docker: ./scripts/docker-up.sh"
  exit 1
fi

log "Native setup complete. Run: ./scripts/native-run.sh"
