#!/usr/bin/env bash
# Delegate to scripts/install.sh (interactive installer).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec bash "$ROOT/scripts/install.sh" "$@"
