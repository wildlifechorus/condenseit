"""RSS and Atom feed collection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

import feedparser
import httpx
import trafilatura

from condenseit.config import FeedConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)


@dataclass
class CollectedArticle:
    url: str
    title: str
    content: str
    source: str
    category: str
    published_at: str
    content_hash: str

    def to_dict(self) -> dict[str, str]:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "category": self.category,
            "content_hash": self.content_hash,
            "published_at": self.published_at,
            "collected_at": datetime.now(UTC).isoformat(),
        }


class RSSCollector:
    def __init__(self, feeds: list[FeedConfig]) -> None:
        self.feeds = feeds
        self.fetch_headers = digest_fetch_headers()
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=self.fetch_headers,
        )

    def collect_feed_results(
        self,
    ) -> list[tuple[FeedConfig, list[CollectedArticle], str | None]]:
        """Per-feed collection; ``error`` is None on success."""
        out: list[tuple[FeedConfig, list[CollectedArticle], str | None]] = []
        for feed in self.feeds:
            try:
                items = self._collect_feed(feed)
                out.append((feed, items, None))
            except Exception as exc:
                logger.exception("Failed to collect feed %s", feed.url)
                out.append((feed, [], str(exc)))
        return out

    def collect_all(self) -> list[CollectedArticle]:
        articles: list[CollectedArticle] = []
        for _feed, items, _err in self.collect_feed_results():
            articles.extend(items)
        return articles

    def _collect_feed(self, feed: FeedConfig) -> list[CollectedArticle]:
        parsed = feedparser.parse(self._fetch_feed_text(feed.url))
        source_title = parsed.feed.get("title", feed.url)
        items: list[CollectedArticle] = []

        for entry in parsed.entries[:15]:
            link = entry.get("link")
            if not link:
                continue
            title = entry.get("title", "Untitled")
            content = self._extract_content(link, entry)
            if not content.strip():
                continue
            published = self._parse_published(entry)
            items.append(
                CollectedArticle(
                    url=link,
                    title=title,
                    content=content,
                    source=source_title,
                    category=feed.category,
                    published_at=published,
                    content_hash=ContentStore.content_hash(content),
                ),
            )
        return items

    def _fetch_feed_text(self, url: str) -> str:
        response = self.client.get(url)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 403:
                raise
            return self._fetch_feed_text_with_urllib(url, exc)
        return response.text

    def _fetch_feed_text_with_urllib(
        self,
        url: str,
        original_exc: httpx.HTTPStatusError,
    ) -> str:
        logger.info("RSS feed %s returned 403 via httpx; retrying with urllib", url)
        request = Request(url, headers=self.fetch_headers)
        try:
            with urlopen(request, timeout=30.0) as response:
                body = response.read()
                encoding = response.headers.get_content_charset() or "utf-8"
        except (OSError, URLError) as exc:
            raise original_exc from exc
        return body.decode(encoding, errors="replace")

    def _extract_content(self, url: str, entry: feedparser.FeedParserDict) -> str:
        try:
            page = self.client.get(url)
            page.raise_for_status()
            extracted = trafilatura.extract(
                page.text,
                include_comments=False,
            )
            if extracted:
                return extracted
        except Exception:
            logger.debug("article fetch failed for %s", url, exc_info=True)
        summary = entry.get("summary", "")
        return summary if isinstance(summary, str) else str(summary)

    @staticmethod
    def _parse_published(entry: feedparser.FeedParserDict) -> str:
        if entry.get("published_parsed"):
            t = entry.published_parsed
            return datetime(*t[:6], tzinfo=UTC).isoformat()
        if entry.get("published"):
            try:
                return parsedate_to_datetime(entry.published).isoformat()
            except (TypeError, ValueError):
                pass
        return datetime.now(UTC).isoformat()


def collect_rss_feeds(feeds: list[FeedConfig]) -> list[dict[str, str]]:
    return [a.to_dict() for a in RSSCollector(feeds).collect_all()]
