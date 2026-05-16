#!/usr/bin/env bash
# Collect feeds on host only (no LLM). Optional: start UI container.
set -euo pipefail
if [[ "${1:-}" == "--with-ui" ]]; then
  shift
  "$(dirname "$0")/docker-up.sh"
fi
exec "$(dirname "$0")/native-dry-run.sh" "$@"
