"""Import read-article URLs from a remote /api/read/export endpoint.

Mirrors the ratings import mechanism so that articles the user marks as read
on the remote SPA are pulled into the local SQLite store before the digest
pipeline runs. The pipeline's ``_filter_read`` step then excludes those URLs
from the next digest.

Environment variables (take priority over YAML config):
    CONDENSEIT_READ_IMPORT_URL           - URL of the remote /api/read/export
    CONDENSEIT_READ_IMPORT_BEARER_TOKEN  - Optional Bearer token for auth
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from condenseit.config import AppConfig
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)


def parse_read_payload(data: Any) -> list[str]:
    """Parse a read-export document into a list of URLs.

    Accepts:
    - ``{"urls": ["https://...", ...]}`` (canonical shape from /api/read/export)
    - A bare JSON list of URL strings
    """
    if isinstance(data, dict):
        raw = data.get("urls")
        if not isinstance(raw, list):
            return []
        return [str(u).strip() for u in raw if isinstance(u, str) and u.strip()]
    if isinstance(data, list):
        return [str(u).strip() for u in data if isinstance(u, str) and u.strip()]
    return []


def import_read_json_text(store: ContentStore, text: str) -> int:
    """Parse JSON text and upsert read URLs. Returns number of rows applied."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        preview = " ".join(text.strip().split())[:120]
        logger.warning(
            "Read import JSON parse error: %s (response starts with %r)",
            exc,
            preview,
        )
        return 0
    urls = parse_read_payload(data)
    applied = 0
    for url in urls:
        store.mark_article_read(url)
        applied += 1
    return applied


def import_read_url(
    store: ContentStore,
    url: str,
    *,
    bearer_token: str = "",
) -> int:
    """GET a JSON document from ``url`` and import read URLs."""
    headers: dict[str, str] = {}
    token = bearer_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            text = response.text
            content_type = response.headers.get("content-type", "").lower()
    except httpx.HTTPError as exc:
        logger.warning("Read import URL failed: %s", exc)
        return 0
    if "application/json" not in content_type and text.lstrip().startswith("<"):
        logger.warning(
            "Read import URL returned HTML instead of JSON "
            "(content-type: %s). Is /api/read proxied to condenseit-web?",
            content_type or "unknown",
        )
        return 0
    return import_read_json_text(store, text)


def apply_configured_read_import(store: ContentStore, config: AppConfig) -> int:
    """Pull read URLs from the configured remote endpoint before a pipeline run.

    Checks ``CONDENSEIT_READ_IMPORT_URL`` env var first, then falls back to
    ``sync.read_import_url`` in YAML config. Returns the number of URLs
    upserted into the local ``read_articles`` table.
    """
    url_raw = (
        os.environ.get("CONDENSEIT_READ_IMPORT_URL", "").strip()
        or config.sync.read_import_url.strip()
    )
    if not url_raw:
        return 0
    bearer = os.environ.get("CONDENSEIT_READ_IMPORT_BEARER_TOKEN", "")
    n = import_read_url(store, url_raw, bearer_token=bearer)
    if n:
        logger.info("Imported %d read URL(s) from remote", n)
    return n
