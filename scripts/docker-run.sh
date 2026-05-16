#!/usr/bin/env bash
# Same as run-with-ollama.sh, but Docker Compose failures are ignored so the
# digest can still run when the UI stack is optional or misconfigured.
set -euo pipefail
export CONDENSEIT_DOCKER_UI_BEST_EFFORT=1
exec "$(dirname "$0")/run-with-ollama.sh" "$@"
