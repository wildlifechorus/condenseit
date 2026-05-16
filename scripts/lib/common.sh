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
