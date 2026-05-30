"""Google News RSS search collector.

Fetches results from Google News's public RSS search endpoint, which supports
search operators such as ``site:``, ``when:``, ``intitle:``, and ``source:``.
No API key is needed.
"""

import logging
from datetime import UTC, datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from condenseit.collectors.article_text import fetch_article_text
from condenseit.collectors.feed_dates import parse_feed_entry_date
from condenseit.collectors.health import collect_with_health
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
            items, entry = collect_with_health(
                rss_url,
                lambda cfg=cfg, rss_url=rss_url: self._collect_source(cfg, rss_url),
                log_label=f"Google News collect failed for query {cfg.query!r}",
            )
            articles.extend(items)
            health.append(entry)
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
            link = entry.get("link", "")
            if not link:
                continue
            title = entry.get("title", "Untitled")
            content = self._extract_content(link, entry)
            if not content.strip():
                continue
            published = self._parse_published(entry)
            items.append(
                {
                    "url": link,
                    "title": title,
                    "content": content,
                    "source": "Google News",
                    "category": cfg.category,
                    "content_hash": ContentStore.content_hash(content),
                    "published_at": published,
                    "collected_at": datetime.now(UTC).isoformat(),
                },
            )
        return items

    def _extract_content(self, url: str, entry: feedparser.FeedParserDict) -> str:
        extracted = fetch_article_text(self._client, url)
        if extracted:
            return extracted
        summary = entry.get("summary", "")
        return summary if isinstance(summary, str) else str(summary)

    @staticmethod
    def _parse_published(entry: feedparser.FeedParserDict) -> str:
        return parse_feed_entry_date(entry)
