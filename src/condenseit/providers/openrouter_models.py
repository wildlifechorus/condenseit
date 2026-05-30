"""Pick a low-cost OpenRouter model from the public catalog."""

import logging
import time
from typing import Any

import httpx

from condenseit.api_urls import OPENROUTER_MODELS_URL

logger = logging.getLogger(__name__)

_CACHE: dict[str, Any] = {"at": 0.0, "model": ""}
_TTL_SEC = 3600


def pick_cheapest_text_model(
    *,
    min_context: int = 8192,
    max_prompt_usd_per_1m: float = 2.0,
) -> str | None:
    """
    Choose a text model with the lowest listed prompt price per token.

    Prices in the API are per-token USD strings; we compare ``prompt`` only.
    """
    now = time.time()
    if _CACHE["model"] and now - float(_CACHE["at"]) < _TTL_SEC:
        return str(_CACHE["model"])

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(OPENROUTER_MODELS_URL)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning("OpenRouter models list failed: %s", exc)
        return None

    best_id: str | None = None
    best_score = float("inf")
    for m in payload.get("data", []):
        arch = m.get("architecture") or {}
        modality = str(arch.get("modality", "")).lower()
        if "text" not in modality:
            continue
        ctx = int(m.get("context_length") or 0)
        if ctx < min_context:
            continue
        mid = str(m.get("id", ""))
        if not mid or mid.endswith("/free") or "embed" in mid.lower():
            continue
        pricing = m.get("pricing") or {}
        raw = pricing.get("prompt")
        try:
            per_token = float(raw or 0)
        except (TypeError, ValueError):
            continue
        if per_token <= 0:
            continue
        per_1m = per_token * 1_000_000
        if per_1m > max_prompt_usd_per_1m:
            continue
        score = per_1m
        if score < best_score:
            best_score = score
            best_id = mid

    if best_id:
        _CACHE["at"] = now
        _CACHE["model"] = best_id
        logger.info(
            "OpenRouter cheapest pick: %s (prompt ~$%.4f / 1M tok)",
            best_id,
            best_score,
        )
    return best_id
