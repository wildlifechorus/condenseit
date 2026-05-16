#!/usr/bin/env bash
# shellcheck shell=bash
# Load vps.* from config.yaml for PWA deploy / bootstrap (DIGEST_PWA_* overrides).
# Requires: ROOT (repo root), PY_BIN (python with condenseit installed).
# Sets: CONFIG_HOST CONFIG_PATH CONFIG_DIGEST_URL CONFIG_DOMAIN

pwa_vps_from_config() {
  local _out
  if ! _out="$(
    cd "$ROOT" && "$PY_BIN" <<'PY'
import shlex
from urllib.parse import urlparse

from condenseit.config import load_config

v = load_config().vps
h = (v.host or "").strip()
p = (v.path or "").strip().rstrip("/")
d = (v.digest_url or "").strip().rstrip("/")
dom = ""
if d:
    dom = urlparse(d).hostname or ""
if not dom:
    dom = "digest.example.com"
print(f"CONFIG_HOST={shlex.quote(h)}")
print(f"CONFIG_PATH={shlex.quote(p)}")
print(f"CONFIG_DIGEST_URL={shlex.quote(d)}")
print(f"CONFIG_DOMAIN={shlex.quote(dom)}")
PY
  )"; then
    printf '%s\n' "ERROR: Failed to read vps.* from config.yaml (cd $ROOT && uv sync)" >&2
    return 1
  fi
  # shellcheck disable=SC1090
  eval "$_out"
}
