#!/usr/bin/env bash
# Print a sanitized view of config (drop lines that look like secret assignments).
set -euo pipefail
# shellcheck source=lib/common.sh
source "$(dirname "$0")/lib/common.sh"
CFG="${CONDENSEIT_CONFIG:-$ROOT/config.yaml}"
if [[ ! -f "$CFG" ]]; then
  echo "No config at $CFG" >&2
  exit 1
fi
grep -Ev '^\s*(api_key|resend_api_key|openrouter_api_key|password)\s*:' "$CFG" || true
