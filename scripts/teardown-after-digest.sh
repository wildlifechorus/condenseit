#!/usr/bin/env bash
# Tear down all resources after a scheduled digest run.
# Stops the Docker web-UI stack and the Ollama Homebrew launch agent.
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
log "Stopping Docker stack (web UI)"
if docker compose ps --quiet 2>/dev/null | grep -q .; then
  docker compose down
  log "Docker stack stopped"
else
  log "Docker stack was not running – nothing to stop"
fi

# ---------------------------------------------------------------------------
# Ollama (Homebrew launch agent: homebrew.mxcl.ollama)
# ---------------------------------------------------------------------------
OLLAMA_SERVICE="homebrew.mxcl.ollama"
log "Stopping Ollama service ($OLLAMA_SERVICE)"
if launchctl list "$OLLAMA_SERVICE" &>/dev/null; then
  launchctl stop "$OLLAMA_SERVICE"
  log "Ollama service stopped"
else
  log "Ollama service was not loaded – nothing to stop"
fi
