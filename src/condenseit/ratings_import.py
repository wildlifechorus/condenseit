"""Import article ratings from JSON files or HTTP URLs into the SQLite store."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from condenseit.config import AppConfig
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)


def parse_ratings_payload(data: Any) -> list[tuple[str, int]]:
    """
    Parse a ratings export document into (url, rating) pairs.

    Accepts:
    - {"ratings": [{"url": "...", "rating": 3}, ...]}
    - {"entries": [...]} (alias)
    - A bare JSON list of objects with url and rating
    """
    pairs: list[tuple[str, int]] = []
    if isinstance(data, dict):
        raw_list = data.get("ratings")
        if not isinstance(raw_list, list):
            raw_list = data.get("entries")
        if not isinstance(raw_list, list):
            return pairs
    elif isinstance(data, list):
        raw_list = data
    else:
        return pairs

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url", "")).strip()
        if not url:
            continue
        try:
            rating = int(item["rating"])
        except (KeyError, TypeError, ValueError):
            continue
        if rating < 1 or rating > 5:
            continue
        pairs.append((url, rating))
    return pairs


def import_ratings_json_text(store: ContentStore, text: str) -> int:
    """Parse JSON text and upsert ratings. Returns number of rows applied."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Ratings JSON parse error: %s", exc)
        return 0
    pairs = parse_ratings_payload(data)
    return store.import_ratings_pairs(pairs)


def import_ratings_path(store: ContentStore, path: Path) -> int:
    """Read a UTF-8 JSON file from disk and import ratings."""
    p = path.expanduser().resolve()
    if not p.is_file():
        logger.warning("Ratings import path is not a file: %s", p)
        return 0
    text = p.read_text(encoding="utf-8")
    return import_ratings_json_text(store, text)


def import_ratings_url(
    store: ContentStore,
    url: str,
    *,
    bearer_token: str = "",
) -> int:
    """GET a JSON document and import ratings."""
    headers: dict[str, str] = {}
    token = bearer_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            text = response.text
    except httpx.HTTPError as exc:
        logger.warning("Ratings import URL failed: %s", exc)
        return 0
    return import_ratings_json_text(store, text)


def apply_configured_ratings_import(store: ContentStore, config: AppConfig) -> int:
    """
    Import ratings from env or sync config before a pipeline run.

    Env overrides YAML when set:
    - CONDENSEIT_RATINGS_IMPORT_PATH
    - CONDENSEIT_RATINGS_IMPORT_URL
    Bearer token only from CONDENSEIT_RATINGS_IMPORT_BEARER_TOKEN (URL fetch).
    """
    total = 0
    path_raw = (
        os.environ.get("CONDENSEIT_RATINGS_IMPORT_PATH", "").strip()
        or config.sync.ratings_import_path.strip()
    )
    if path_raw:
        n = import_ratings_path(store, Path(path_raw))
        total += n
        if n:
            logger.info("Imported %d ratings from path %s", n, path_raw)

    url_raw = (
        os.environ.get("CONDENSEIT_RATINGS_IMPORT_URL", "").strip()
        or config.sync.ratings_import_url.strip()
    )
    if url_raw:
        bearer = os.environ.get("CONDENSEIT_RATINGS_IMPORT_BEARER_TOKEN", "")
        n = import_ratings_url(store, url_raw, bearer_token=bearer)
        total += n
        if n:
            logger.info("Imported %d ratings from URL", n)
    return total
