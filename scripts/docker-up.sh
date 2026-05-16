#!/usr/bin/env bash
# Start web UI only (digest + admin + ratings). No Ollama in Docker.
# CONDENSEIT_DOCKER_UI_BEST_EFFORT=1: ignore compose failures (used by docker-run.sh).
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
mkdir -p data/digests
log "Starting CondenseIt web UI on :8899"
if [[ "${CONDENSEIT_DOCKER_UI_BEST_EFFORT:-}" == "1" ]]; then
  docker compose up -d --build 2>/dev/null || true
else
  docker compose up -d --build
fi
log "Digest: http://localhost:8899/"
log "Admin:  http://localhost:8899/admin/"
log "Run pipeline on host: ./scripts/native-run.sh"
