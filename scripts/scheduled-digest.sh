#!/usr/bin/env bash
# Scheduled digest wrapper.
# 1. Ensures Ollama is running (starts it via launchd if needed).
# 2. Runs: make run-with-ollama-pwa-deploy
# 3. Always tears down Docker + Ollama when done, even on failure.
#
# Usage:
#   ./scripts/scheduled-digest.sh
#   (Normally invoked by the launchd agent at 06:00 and 21:00.)
set -euo pipefail
source "$(dirname "$0")/lib/common.sh"

# ---------------------------------------------------------------------------
# Logging to file (~/Library/Logs/condenseit-digest.log)
# ---------------------------------------------------------------------------
LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/condenseit-digest.log"
mkdir -p "$LOG_DIR"
# Trim digest log before we append (safe: nothing holds this path yet).
bash "$(dirname "$0")/cleanup-condenseit-logs.sh" digest-pre-run
exec > >(tee -a "$LOG_FILE") 2>&1
echo ""
echo "============================================================"
echo "[condenseit] Scheduled digest started at $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

TEARDOWN_SCRIPT="$(dirname "$0")/teardown-after-digest.sh"
OLLAMA_SERVICE="homebrew.mxcl.ollama"
OLLAMA_MAX_WAIT=60   # seconds to wait for Ollama to become ready
OLLAMA_POLL=3        # poll interval in seconds

# ---------------------------------------------------------------------------
# Ensure teardown always runs
# ---------------------------------------------------------------------------
cleanup() {
  echo ""
  log "Running teardown (exit code: $?)"
  bash "$TEARDOWN_SCRIPT" || true
  echo "[condenseit] Finished at $(date '+%Y-%m-%d %H:%M:%S')"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Start Ollama if it is not already running
# ---------------------------------------------------------------------------
log "Checking Ollama service"
if ! launchctl list "$OLLAMA_SERVICE" &>/dev/null; then
  log "Ollama not loaded – starting $OLLAMA_SERVICE"
  launchctl start "$OLLAMA_SERVICE"
fi

# Wait for the Ollama HTTP API to become reachable
log "Waiting for Ollama to be ready (up to ${OLLAMA_MAX_WAIT}s)"
WAITED=0
until curl -sf http://localhost:11434/ &>/dev/null; do
  if (( WAITED >= OLLAMA_MAX_WAIT )); then
    log "ERROR: Ollama did not become ready within ${OLLAMA_MAX_WAIT}s – aborting"
    exit 1
  fi
  sleep "$OLLAMA_POLL"
  WAITED=$(( WAITED + OLLAMA_POLL ))
done
log "Ollama is ready"

# ---------------------------------------------------------------------------
# Run the digest + PWA deploy
# ---------------------------------------------------------------------------
log "Starting: make run-with-ollama-pwa-deploy"
make -C "$ROOT" run-with-ollama-pwa-deploy
