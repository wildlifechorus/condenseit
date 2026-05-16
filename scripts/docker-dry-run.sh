#!/usr/bin/env bash
# Alias for run-without-ollama.sh (no --with-ui). Kept for Makefile and habits.
set -euo pipefail
exec "$(dirname "$0")/run-without-ollama.sh" "$@"
