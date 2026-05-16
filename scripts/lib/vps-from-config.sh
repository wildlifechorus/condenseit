#!/usr/bin/env bash
# =============================================================
# lib/vps-from-config.sh - Read vps.* fields from config.yaml
#
# Populates the following shell variables when called via
# `vps_from_config`:
#   CONFIG_HOST        vps.host
#   CONFIG_PATH        vps.path
#   CONFIG_DIGEST_URL  vps.digest_url
#   CONFIG_DOMAIN      domain extracted from digest_url
# =============================================================

vps_from_config() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

  local py_bin=""
  if [[ -x "$root/.venv/bin/python" ]]; then
    py_bin="$root/.venv/bin/python"
  elif command -v python3 &>/dev/null; then
    py_bin="$(command -v python3)"
  else
    echo "vps-from-config: python3 not found" >&2
    return 1
  fi

  local config_arg=""
  if [[ -n "${CONDENSEIT_CONFIG:-}" ]]; then
    config_arg="$CONDENSEIT_CONFIG"
  elif [[ -f "$root/config.yaml" ]]; then
    config_arg="$root/config.yaml"
  elif [[ -f "$root/config.example.yaml" ]]; then
    config_arg="$root/config.example.yaml"
  fi

  local result
  result="$("$py_bin" - "$config_arg" <<'PYEOF'
import sys, os, re, yaml
from pathlib import Path

config_path = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else ""

env_pattern = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')

def expand(val):
    if not isinstance(val, str):
        return val
    def rep(m):
        v = os.environ.get(m.group(1))
        if v is not None:
            return v
        return m.group(2) or ""
    return env_pattern.sub(rep, val)

raw = {}
for p in ([config_path] if config_path else []):
    if Path(p).exists():
        raw = yaml.safe_load(Path(p).read_text()) or {}
        break

vps = raw.get("vps", {})
host = expand(str(vps.get("host", "")))
path = expand(str(vps.get("path", "")))
digest_url = expand(str(vps.get("digest_url", "")))

import re as _re
m = _re.search(r'https?://([^/]+)', digest_url)
domain = m.group(1) if m else ""

print(f"CONFIG_HOST={host}")
print(f"CONFIG_PATH={path}")
print(f"CONFIG_DIGEST_URL={digest_url}")
print(f"CONFIG_DOMAIN={domain}")
PYEOF
    )"

  local exit_code=$?
  if [[ $exit_code -ne 0 ]]; then
    echo "vps-from-config: python script failed" >&2
    return 1
  fi

  while IFS='=' read -r key value; do
    case "$key" in
      CONFIG_HOST)        CONFIG_HOST="$value" ;;
      CONFIG_PATH)        CONFIG_PATH="$value" ;;
      CONFIG_DIGEST_URL)  CONFIG_DIGEST_URL="$value" ;;
      CONFIG_DOMAIN)      CONFIG_DOMAIN="$value" ;;
    esac
  done <<< "$result"

  return 0
}
