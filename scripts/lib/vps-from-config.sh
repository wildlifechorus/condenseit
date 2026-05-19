#!/usr/bin/env bash
# =============================================================
# lib/vps-from-config.sh - Read vps.* fields from config.yaml
#
# Functions:
#
#   vps_from_config
#     Reads the top-level vps: block. Populates:
#       CONFIG_HOST, CONFIG_PATH, CONFIG_DIGEST_URL, CONFIG_DOMAIN
#
#   vps_list_instances
#     Prints "name|label" lines for every entry in instances:.
#     Falls back to a single synthetic "default" line from the top-level
#     vps: block when instances: is absent.
#
#   vps_from_config_instance NAME
#     Reads instances.<NAME>.vps from config.yaml. Populates:
#       CONFIG_HOST, CONFIG_PATH, CONFIG_DIGEST_URL, CONFIG_DOMAIN,
#       CONFIG_PORT, CONFIG_APP_DIR, CONFIG_SERVICE, CONFIG_LABEL
#     Falls back to the top-level vps: block when instances: is absent.
# =============================================================

_vps_py_bin() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  if [[ -x "$root/.venv/bin/python" ]]; then
    echo "$root/.venv/bin/python"
  elif command -v python3 &>/dev/null; then
    command -v python3
  else
    echo "vps-from-config: python3 not found" >&2
    return 1
  fi
}

_vps_config_path() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  if [[ -n "${CONDENSEIT_CONFIG:-}" ]]; then
    echo "$CONDENSEIT_CONFIG"
  elif [[ -f "$root/config.yaml" ]]; then
    echo "$root/config.yaml"
  elif [[ -f "$root/config.example.yaml" ]]; then
    echo "$root/config.example.yaml"
  fi
}

vps_from_config() {
  local py_bin config_arg result

  py_bin="$(_vps_py_bin)" || return 1
  config_arg="$(_vps_config_path)"

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

# ---------------------------------------------------------------------------
# vps_list_instances - print "name|label" for each instances: entry
# ---------------------------------------------------------------------------
vps_list_instances() {
  local py_bin config_arg

  py_bin="$(_vps_py_bin)" || return 1
  config_arg="$(_vps_config_path)"

  "$py_bin" - "$config_arg" <<'PYEOF'
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

instances = raw.get("instances", {})
if instances:
    for name, cfg in instances.items():
        label = expand(str(cfg.get("label", name)))
        print(f"{name}|{label}")
else:
    # Fall back: synthesize a single entry from the top-level vps: block.
    vps = raw.get("vps", {})
    digest_url = expand(str(vps.get("digest_url", "")))
    import re as _re
    m = _re.search(r'https?://([^/]+)', digest_url)
    domain = m.group(1) if m else "default"
    print(f"default|{domain}")
PYEOF
}

# ---------------------------------------------------------------------------
# vps_from_config_instance NAME - populate vars for a named instance
# ---------------------------------------------------------------------------
vps_from_config_instance() {
  local instance_name="$1"
  local py_bin config_arg result

  py_bin="$(_vps_py_bin)" || return 1
  config_arg="$(_vps_config_path)"

  result="$("$py_bin" - "$config_arg" "$instance_name" <<'PYEOF'
import sys, os, re, yaml
from pathlib import Path

config_path    = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else ""
instance_name  = sys.argv[2] if len(sys.argv) > 2 else ""

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

instances = raw.get("instances", {})

if instances and instance_name and instance_name in instances:
    cfg  = instances[instance_name]
    vps  = cfg.get("vps", {})
    label = expand(str(cfg.get("label", instance_name)))
    host       = expand(str(vps.get("host", "")))
    path       = expand(str(vps.get("path", "")))
    digest_url = expand(str(vps.get("digest_url", "")))
    port       = expand(str(vps.get("port", "8765")))
    app_dir    = expand(str(vps.get("app_dir", "~/condenseit")))
    service    = expand(str(vps.get("service", "condenseit-web")))
else:
    # Fall back to top-level vps: block.
    vps        = raw.get("vps", {})
    label      = "default"
    host       = expand(str(vps.get("host", "")))
    path       = expand(str(vps.get("path", "")))
    digest_url = expand(str(vps.get("digest_url", "")))
    port       = "8765"
    app_dir    = "~/condenseit"
    service    = "condenseit-web"

import re as _re
m = _re.search(r'https?://([^/]+)', digest_url)
domain = m.group(1) if m else ""

print(f"CONFIG_HOST={host}")
print(f"CONFIG_PATH={path}")
print(f"CONFIG_DIGEST_URL={digest_url}")
print(f"CONFIG_DOMAIN={domain}")
print(f"CONFIG_PORT={port}")
print(f"CONFIG_APP_DIR={app_dir}")
print(f"CONFIG_SERVICE={service}")
print(f"CONFIG_LABEL={label}")
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
      CONFIG_PORT)        CONFIG_PORT="$value" ;;
      CONFIG_APP_DIR)     CONFIG_APP_DIR="$value" ;;
      CONFIG_SERVICE)     CONFIG_SERVICE="$value" ;;
      CONFIG_LABEL)       CONFIG_LABEL="$value" ;;
    esac
  done <<< "$result"

  return 0
}
