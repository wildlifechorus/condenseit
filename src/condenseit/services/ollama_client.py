"""HTTP helpers for Ollama admin actions."""

from __future__ import annotations

from typing import Any

import httpx


def ollama_list_tags(host: str) -> list[str]:
    base = host.rstrip("/")
    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{base}/api/tags")
        r.raise_for_status()
        data = r.json()
    models = data.get("models", [])
    return sorted({str(m.get("name", "")) for m in models if m.get("name")})


def ollama_pull(host: str, model: str) -> dict[str, Any]:
    base = host.rstrip("/")
    with httpx.Client(timeout=600.0) as client:
        r = client.post(f"{base}/api/pull", json={"name": model.strip()})
        r.raise_for_status()
        return r.json() if r.content else {}


def ollama_delete(host: str, model: str) -> dict[str, Any]:
    base = host.rstrip("/")
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{base}/api/delete", json={"name": model.strip()})
        r.raise_for_status()
        return r.json() if r.content else {}
