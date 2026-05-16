"""Google News RSS search collector.

Fetches results from Google News's public RSS search endpoint, which supports
search operators such as ``site:``, ``when:``, ``intitle:``, and ``source:``.
No API key is needed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import httpx
import trafilatura

from condenseit.config import GoogleNewsSearchConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

_BASE_URL = "https://news.google.com/rss/search"
_MAX_ENTRIES = 15


def build_gnews_url(config: GoogleNewsSearchConfig) -> str:
    """Return the Google News RSS search URL for ``config``."""
    lang = config.language.lower()
    country = config.country.upper()
    return (
        f"{_BASE_URL}?q={quote_plus(config.query)}"
        f"&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"
    )


class GoogleNewsCollector:
    """Collect articles from Google News RSS search queries."""

    def __init__(self, sources: list[GoogleNewsSearchConfig]) -> None:
        self.sources = sources
        self._headers = digest_fetch_headers()
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=self._headers,
        )

    def collect_all_with_health(
        self,
    ) -> tuple[list[dict[str, str]], list[tuple[str, str | None, int]]]:
        """Return ``(articles, [(rss_url, error_or_none, item_count), ...])``."""
        articles: list[dict[str, str]] = []
        health: list[tuple[str, str | None, int]] = []
        for cfg in self.sources:
            rss_url = build_gnews_url(cfg)
            try:
                items = self._collect_source(cfg, rss_url)
                articles.extend(items)
                health.append((rss_url, None, len(items)))
            except Exception as exc:
                logger.exception('Google News collect failed for query %r', cfg.query)
                health.append((rss_url, str(exc), 0))
        return articles, health

    def _collect_source(
        self,
        cfg: GoogleNewsSearchConfig,
        rss_url: str,
    ) -> list[dict[str, str]]:
        resp = self._client.get(rss_url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        items: list[dict[str, str]] = []

        for entry in feed.entries[:_MAX_ENTRIES]:
            link = entry.get('link', '')
            if not link:
                continue
            title = entry.get('title', 'Untitled')
            content = self._extract_content(link, entry)
            if not content.strip():
                continue
            published = self._parse_published(entry)
            items.append(
                {
                    'url': link,
                    'title': title,
                    'content': content,
                    'source': 'Google News',
                    'category': cfg.category,
                    'content_hash': ContentStore.content_hash(content),
                    'published_at': published,
                    'collected_at': datetime.now(UTC).isoformat(),
                },
            )
        return items

    def _extract_content(self, url: str, entry: feedparser.FeedParserDict) -> str:
        try:
            page = self._client.get(url)
            page.raise_for_status()
            extracted = trafilatura.extract(page.text, include_comments=False)
            if extracted:
                return extracted
        except Exception:
            logger.debug('Article fetch failed for %s', url, exc_info=True)
        summary = entry.get('summary', '')
        return summary if isinstance(summary, str) else str(summary)

    @staticmethod
    def _parse_published(entry: feedparser.FeedParserDict) -> str:
        if entry.get('published_parsed'):
            t = entry.published_parsed
            return datetime(*t[:6], tzinfo=UTC).isoformat()
        if entry.get('published'):
            try:
                return parsedate_to_datetime(entry.published).isoformat()
            except (TypeError, ValueError):
                pass
        return datetime.now(UTC).isoformat()
