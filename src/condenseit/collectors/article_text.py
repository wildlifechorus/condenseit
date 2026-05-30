"""Shared article body extraction for collectors."""

import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)


def fetch_article_text(client: httpx.Client, url: str) -> str | None:
    """Return extracted article text, or None when fetch/extraction fails."""
    try:
        page = client.get(url)
        page.raise_for_status()
        extracted = trafilatura.extract(page.text, include_comments=False)
        if extracted:
            return extracted
    except Exception as exc:
        logger.debug("Article fetch failed for %s: %s", url, exc)
    return None
