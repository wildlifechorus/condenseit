#!/usr/bin/env bash
# Start web UI only (digest + admin + ratings). No Ollama in Docker.
# CONDENSEIT_DOCKER_UI_BEST_EFFORT=1: ignore compose failures (used by docker-run.sh).
# CONDENSEIT_DOCKER_BUILD=1: build from source instead of pull + up.
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
mkdir -p data/digests
log "Starting CondenseIt web UI on :8899"

compose_up() {
  if [[ "${CONDENSEIT_DOCKER_BUILD:-}" == "1" ]]; then
    docker compose up -d --build
  else
    docker compose pull || true
    docker compose up -d
  fi
}

if [[ "${CONDENSEIT_DOCKER_UI_BEST_EFFORT:-}" == "1" ]]; then
  compose_up 2>/dev/null || true
else
  compose_up
fi
log "Digest: http://localhost:8899/"
log "Admin:  http://localhost:8899/admin/"
log "Run pipeline on host: ./scripts/native-run.sh"
