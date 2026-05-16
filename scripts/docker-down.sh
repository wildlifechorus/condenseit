#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"
log "Stopping Docker stack"
docker compose down
