"""Website change detection."""

import logging
from difflib import unified_diff

import httpx
import trafilatura

from condenseit.config import WatchUrlConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)


def _fetch_text(url: str) -> str:
    response = httpx.get(
        url,
        timeout=30.0,
        follow_redirects=True,
        headers=digest_fetch_headers(),
    )
    response.raise_for_status()
    downloaded = response.text
    text = trafilatura.extract(downloaded, include_comments=False)
    return text or downloaded[:8000]


def _meaningful_change(
    old: str,
    new: str,
    threshold: float,
) -> bool:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = list(unified_diff(old_lines, new_lines))
    if not old_lines:
        return bool(new_lines)
    change_ratio = len(diff) / max(len(old_lines), 1)
    return change_ratio > threshold


def check_website_changes(
    watch_urls: list[WatchUrlConfig],
    store: ContentStore,
) -> list[dict[str, str]]:
    changes, _health = check_website_changes_with_health(watch_urls, store)
    return changes


def check_website_changes_with_health(
    watch_urls: list[WatchUrlConfig],
    store: ContentStore,
) -> tuple[list[dict[str, str]], list[tuple[str, str | None, int]]]:
    """Return ``(change_events, [(url, error_or_none, snapshot_bytes), ...])``."""
    changes: list[dict[str, str]] = []
    health: list[tuple[str, str | None, int]] = []
    for item in watch_urls:
        try:
            current = _fetch_text(item.url)
            previous = store.get_snapshot(item.url)
            if previous is None:
                store.save_snapshot(item.url, current)
                changes.append(
                    {
                        "url": item.url,
                        "category": item.category,
                        "status": "new",
                        "snippet": current[:500],
                    },
                )
                health.append((item.url, None, len(current)))
                continue
            if _meaningful_change(
                previous["content"],
                current,
                item.change_threshold,
            ):
                store.save_snapshot(item.url, current)
                changes.append(
                    {
                        "url": item.url,
                        "category": item.category,
                        "status": "changed",
                        "snippet": current[:500],
                    },
                )
            health.append((item.url, None, len(current)))
        except Exception as exc:
            logger.exception("Change check failed for %s", item.url)
            health.append((item.url, str(exc), 0))
    return changes, health
