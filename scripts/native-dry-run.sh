#!/usr/bin/env bash
# Collect and rank only — no LLM.
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
ensure_config
ensure_venv
log "Dry run (no LLM)"
condenseit run --dry-run "$@"
