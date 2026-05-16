#!/usr/bin/env bash
# Trim CondenseIt digest log files so they do not grow without bound.
#
# Modes (first argument):
#   digest-pre-run  Only ~/Library/Logs/condenseit-digest.log. Call this
#                   before opening that file for append (scheduled-digest.sh).
#   all-safe        Trim known logs when no other process has them open.
#                   Safe for: make logs-clean (agent idle or between runs).
#
# Environment overrides:
#   CONDENSEIT_LOG_DIR         default: ~/Library/Logs
#   CONDENSEIT_LOG_MAX_BYTES   default: 5242880  (5 MiB)
#   CONDENSEIT_LOG_KEEP_BYTES  default: 2097152  (2 MiB tail after trim)
set -euo pipefail

source "$(dirname "$0")/lib/common.sh"

MODE="${1:-all-safe}"
LOG_DIR="${CONDENSEIT_LOG_DIR:-$HOME/Library/Logs}"
MAX_BYTES="${CONDENSEIT_LOG_MAX_BYTES:-$((5 * 1024 * 1024))}"
KEEP_BYTES="${CONDENSEIT_LOG_KEEP_BYTES:-$((2 * 1024 * 1024))}"

DIGEST_LOG="$LOG_DIR/condenseit-digest.log"
LAUNCHD_LOG="$LOG_DIR/condenseit-digest-launchd.log"

# ---------------------------------------------------------------------------
# Portable file size in bytes (0 if missing).
# ---------------------------------------------------------------------------
file_size_bytes() {
  local path="$1"
  if [[ "$(uname -s)" == "Darwin" ]]; then
    stat -f%z "$path" 2>/dev/null || printf '0'
  else
    stat -c%s "$path" 2>/dev/null || printf '0'
  fi
}

# ---------------------------------------------------------------------------
# True if any process has this path open (best-effort).
# ---------------------------------------------------------------------------
path_is_open() {
  local path="$1"
  if lsof -- "$path" 2>/dev/null | awk 'NR > 1 { exit 0 } END { exit 1 }'; then
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Remove stale temp files from interrupted trims.
# ---------------------------------------------------------------------------
remove_stale_temps() {
  local base="$1"
  local f
  shopt -s nullglob
  for f in "${base}.tmp."*; do
    if [[ -f "$f" ]]; then
      log "Removing stale temp log: $f"
      rm -f "$f"
    fi
  done
  shopt -u nullglob
}

# ---------------------------------------------------------------------------
# If log is larger than MAX_BYTES, replace with last KEEP_BYTES of content.
# force=1: skip the "is another process using this file?" check.
# ---------------------------------------------------------------------------
trim_log() {
  local path="$1"
  local force="${2:-0}"

  if [[ ! -f "$path" ]]; then
    return 0
  fi

  remove_stale_temps "$path"

  local size
  size="$(file_size_bytes "$path")"
  if (( size <= MAX_BYTES )); then
    return 0
  fi

  if [[ "$force" != "1" ]] && path_is_open "$path"; then
    log "Skipping log trim (file in use): $path"
    return 0
  fi

  log "Trimming log (${size} bytes → last ${KEEP_BYTES} bytes): $path"
  local tmp="${path}.tmp.$$"
  tail -c "$KEEP_BYTES" "$path" >"$tmp"
  mv "$tmp" "$path"
}

case "$MODE" in
  digest-pre-run)
    trim_log "$DIGEST_LOG" 1
    ;;
  all-safe)
    trim_log "$DIGEST_LOG" 0
    trim_log "$LAUNCHD_LOG" 0
    ;;
  *)
    log "Usage: $0 digest-pre-run | all-safe"
    exit 1
    ;;
esac
