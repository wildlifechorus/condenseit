#!/usr/bin/env bash
# Interactive install helper: prerequisites, example configs, schedule snippets.
#
# Usage:
#   bash scripts/install.sh
#   INSTALLER_NONINTERACTIVE=1 bash scripts/install.sh
#
# Environment (non-interactive mode):
#   INSTALL_DIR          repo root (default: auto-detected)
#   INSTALLER_FIRST_TIME first run time (default: 09:00)
#   INSTALLER_CADENCE    runs per day 1|2|3 (default: 1)
#   INSTALLER_SKIP_COPY  if 1, do not offer config copies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

prompt() {
  # $1 default value, $2 prompt text
  local _def="$1"
  local _text="$2"
  local _line
  if [[ -n "${INSTALLER_NONINTERACTIVE:-}" ]]; then
    printf '%s\n' "$_def"
    return
  fi
  read -r -p "$_text [${_def}]: " _line || true
  if [[ -z "${_line}" ]]; then
    printf '%s\n' "$_def"
  else
    printf '%s\n' "$_line"
  fi
}

confirm() {
  # $1 default y or n
  local _def="$1"
  local _msg="$2"
  local _line
  if [[ -n "${INSTALLER_NONINTERACTIVE:-}" ]]; then
    [[ "$_def" == 'y' ]] && return 0
    return 1
  fi
  read -r -p "$_msg (y/n) [${_def}]: " _line || true
  _line="$(printf '%s' "${_line:-}" | tr '[:upper:]' '[:lower:]')"
  if [[ -z "$_line" ]]; then
    _line="$_def"
  fi
  [[ "$_line" == 'y' || "$_line" == 'yes' ]]
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

check_python() {
  have_cmd python3 || die 'python3 not found. Install Python 3.11 or newer.'
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
    || die 'Python 3.11+ required (see pyproject.toml requires-python).'
}

check_uv() {
  have_cmd uv || die 'uv not found. Install: https://docs.astral.sh/uv/'
}

is_all_digits() {
  local x="$1"
  [[ -n "$x" ]] || return 1
  case "$x" in *[!0-9]*) return 1;; *) return 0;; esac
}

# Parse time into H24 (0-23) and MIN (0-59). Accepts 09:00, 9:30pm, 21:00, 9am.
# Uses string splits and case checks (macOS bash 3.2 =~ lacks + and {m,n}).
parse_time_to_hm() {
  local s
  s="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')"
  [[ -n "$s" ]] || return 1

  local ap=''
  if [[ "$s" == *pm ]]; then
    ap='pm'
    s="${s%pm}"
  elif [[ "$s" == *am ]]; then
    ap='am'
    s="${s%am}"
  fi

  local h m
  if [[ "$s" == *:* ]]; then
    h="${s%%:*}"
    m="${s#*:}"
  else
    [[ -n "$s" ]] || return 1
    [[ -z "$ap" ]] && return 1
    h="$s"
    m='0'
  fi

  is_all_digits "$h" || return 1
  is_all_digits "$m" || return 1
  if ((10#$m < 0 || 10#$m > 59)); then
    return 1
  fi
  h=$((10#$h))
  m=$((10#$m))

  if [[ "$ap" == 'pm' ]]; then
    if ((h < 1 || h > 12)); then
      return 1
    fi
    if ((h != 12)); then
      h=$((h + 12))
    fi
  elif [[ "$ap" == 'am' ]]; then
    if ((h < 1 || h > 12)); then
      return 1
    fi
    if ((h == 12)); then
      h=0
    fi
  else
    if ((h < 0 || h > 23)); then
      return 1
    fi
  fi

  printf '%d %d' "$h" "$m"
}

minutes_from_midnight() {
  local h="$1"
  local m="$2"
  printf '%d' $((h * 60 + m))
}

hm_from_minutes() {
  local t="$1"
  local h m
  t=$((t % 1440))
  if ((t < 0)); then
    t=$((t + 1440))
  fi
  h=$((t / 60))
  m=$((t % 60))
  printf '%d %d' "$h" "$m"
}

format_hm() {
  local h="$1"
  local m="$2"
  printf '%02d:%02d' "$h" "$m"
}

compute_run_times() {
  local cadence="$1"
  local h0="$2"
  local m0="$3"
  local start
  local interval k t th tm _pair

  start="$(minutes_from_midnight "$h0" "$m0")"
  interval=$((1440 / cadence))

  for ((k = 0; k < cadence; k++)); do
    t=$((start + k * interval))
    _pair="$(hm_from_minutes "$t")"
    th="${_pair%% *}"
    tm="${_pair#* }"
    printf '%s\n' "$(format_hm "$th" "$tm")"
  done
}

cron_line() {
  local hm="$1"
  local install_dir="$2"
  local uv_path="$3"
  local h m
  IFS=':' read -r h m <<<"$hm"
  h=$((10#$h))
  m=$((10#$m))
  printf '%d %d * * * cd %q && %q run condenseit run\n' \
    "$m" "$h" "$install_dir" "$uv_path"
}

emit_launchd_snippet() {
  local install_dir="$1"
  local uv_path="$2"
  shift 2
  local times=("$@")

  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <!-- Edit paths if you move the repo or uv binary. -->
  <key>Label</key>
  <string>com.condenseit.digest</string>
  <key>ProgramArguments</key>
  <array>
    <string>${uv_path}</string>
    <string>run</string>
    <string>condenseit</string>
    <string>run</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${install_dir}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>
EOF

  local hm h m
  for hm in "${times[@]}"; do
    IFS=':' read -r h m <<<"$hm"
    h=$((10#$h))
    m=$((10#$m))
    cat <<EOF
    <dict>
      <key>Hour</key>
      <integer>${h}</integer>
      <key>Minute</key>
      <integer>${m}</integer>
    </dict>
EOF
  done

  cat <<EOF
  </array>
  <key>StandardOutPath</key>
  <string>/tmp/condenseit-digest.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/condenseit-digest.err</string>
</dict>
</plist>
EOF
}

maybe_copy_examples() {
  local root="$1"
  if [[ -n "${INSTALLER_SKIP_COPY:-}" ]]; then
    return 0
  fi
  if [[ -f "$root/config.yaml" && -f "$root/.env" ]]; then
    printf 'config.yaml and .env already exist; skipping copy offers.\n'
    return 0
  fi

  if ! confirm 'n' 'Copy missing example files (config.yaml / .env)?'; then
    return 0
  fi

  if [[ ! -f "$root/config.yaml" ]]; then
    if [[ -f "$root/config.example.yaml" ]]; then
      cp "$root/config.example.yaml" "$root/config.yaml"
      printf 'Created %s/config.yaml from config.example.yaml\n' "$root"
    else
      printf 'WARN: missing %s/config.example.yaml\n' "$root"
    fi
  fi

  if [[ ! -f "$root/.env" ]]; then
    if [[ -f "$root/.env.example" ]]; then
      cp "$root/.env.example" "$root/.env"
      printf 'Created %s/.env from .env.example\n' "$root"
    else
      printf 'WARN: missing %s/.env.example\n' "$root"
    fi
  fi
}

main() {
  printf 'CondenseIt installer (configs + schedule snippets)\n\n'

  check_python
  check_uv

  local install_dir
  install_dir="$(prompt "${INSTALL_DIR:-$DEFAULT_ROOT}" \
    'Repository / install directory (used for cd and launchd WorkingDirectory)')"
  install_dir="$(cd "$install_dir" && pwd)"

  [[ -f "$install_dir/pyproject.toml" ]] \
    || die "No pyproject.toml in $install_dir (wrong directory?)"

  maybe_copy_examples "$install_dir"

  local uv_path
  uv_path="$(command -v uv)"

  local first_in cadence_in
  first_in="${INSTALLER_FIRST_TIME:-}"
  cadence_in="${INSTALLER_CADENCE:-}"
  if [[ -z "$first_in" ]]; then
    first_in="$(prompt '09:00' \
      'First digest time (24h like 21:30, or 9:30pm)')"
  fi
  if [[ -z "$cadence_in" ]]; then
    cadence_in="$(prompt '1' 'Runs per day (1, 2, or 3; evenly spaced after first time)')"
  fi

  local h0 m0 _pair
  _pair="$(parse_time_to_hm "$first_in")" || \
    die "Could not parse time: $first_in (try 09:00 or 9:00pm)"
  h0="${_pair%% *}"
  m0="${_pair#* }"

  local cadence="$cadence_in"
  if [[ ! "$cadence" =~ ^[123]$ ]]; then
    die "Cadence must be 1, 2, or 3 (got: $cadence)"
  fi

  local -a run_times=()
  local line
  while IFS= read -r line; do
    run_times+=("$line")
  done <<<"$(compute_run_times "$cadence" "$h0" "$m0")"

  printf '\n--- Schedule (even spacing) ---\n'
  printf 'Times: %s\n' "${run_times[*]}"
  printf '\n--- Append to crontab (crontab -e) ---\n'
  local hm
  for hm in "${run_times[@]}"; do
    cron_line "$hm" "$install_dir" "$uv_path"
  done

  printf '\n--- macOS LaunchAgent plist (save and edit paths if needed) ---\n'
  emit_launchd_snippet "$install_dir" "$uv_path" "${run_times[@]}"

  local plist_path
  plist_path="${HOME}/Library/LaunchAgents/com.condenseit.digest.plist"
  if [[ "$(uname -s)" == 'Darwin' ]] && confirm 'n' \
    "Write plist to ${plist_path} ?"; then
    if [[ -f "$plist_path" ]]; then
      confirm 'n' "${plist_path} exists. Overwrite?" \
        || die 'Aborted (plist not written).'
    fi
    mkdir -p "${HOME}/Library/LaunchAgents"
    emit_launchd_snippet "$install_dir" "$uv_path" "${run_times[@]}" \
      >"$plist_path"
    printf '\nWrote %s\n' "$plist_path"
    printf 'Load with: launchctl load %q\n' "$plist_path"
  fi

  printf '\nDone. See docs/installation.md and docs/scheduling.md\n'
}

main "$@"
