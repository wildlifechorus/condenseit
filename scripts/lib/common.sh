#!/usr/bin/env bash
# Shared helpers for CondenseIt scripts.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

log() {
  printf '\n[condenseit] %s\n' "$*"
}

ensure_config() {
  if [[ ! -f config.yaml ]]; then
    log "Creating config.yaml from config.example.yaml"
    cp config.example.yaml config.yaml
  fi
}

ensure_venv() {
  if [[ ! -d .venv ]]; then
    log "Creating Python virtualenv"
    python3 -m venv .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -e .
}

ensure_frontend() {
  # Force rebuild if the dist looks like an old PWA build (has service worker,
  # workbox artifacts, or manifest.webmanifest from vite-plugin-pwa which was
  # removed).
  local stale=false
  if [[ -f frontend/dist/sw.js ]] || \
     [[ -f frontend/dist/manifest.webmanifest ]] || \
     ls frontend/dist/assets/workbox-*.js &>/dev/null 2>&1; then
    log "Stale PWA build detected - rebuilding frontend..."
    stale=true
    rm -rf frontend/dist
  fi

  if [[ ! -d frontend/dist ]] || [[ "$stale" == true ]]; then
    log "Building frontend..."
    if ! command -v node &>/dev/null; then
      log "WARNING: node not found - web UI will fall back to Jinja2 templates."
      return 0
    fi
    (cd frontend && npm ci --silent && npm run build)
    log "Frontend built."
  fi
}
