#!/usr/bin/env bash
# Web UI in Docker + full digest on host via native Ollama (Metal).
# Optional first arg: native (digest only) or docker (drop that token only).
set -euo pipefail
MODE="${1:-}"
if [[ "$MODE" == "native" ]]; then
  shift || true
  exec "$(dirname "$0")/native-run.sh" "$@"
fi
if [[ "$MODE" == "docker" ]]; then
  shift || true
fi
"$(dirname "$0")/docker-up.sh"
"$(dirname "$0")/native-run.sh" "$@"
