"""Podcast episode collector via RSS/Atom feeds with iTunes namespace support."""

from __future__ import annotations

import html
import logging
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from condenseit.config import PodcastConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 10


def _strip_html(raw: str) -> str:
    """Strip HTML tags and unescape entities, returning plain text."""
    plain = re.sub(r"<[^>]+>", " ", raw)
    plain = html.unescape(plain)
    return re.sub(r"\s+", " ", plain).strip()


class PodcastCollector:
    """Collect podcast episodes from RSS/Atom feeds with iTunes extensions."""

    def __init__(self, sources: list[PodcastConfig]) -> None:
        self.sources = sources
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=digest_fetch_headers(),
        )

    def collect_all_with_health(
        self,
    ) -> tuple[list[dict[str, str]], list[tuple[str, str | None, int]]]:
        """Return ``(articles, [(feed_url, error_or_none, item_count), ...])``."""
        articles: list[dict[str, str]] = []
        health: list[tuple[str, str | None, int]] = []
        for cfg in self.sources:
            try:
                items = self._collect_feed(cfg)
                articles.extend(items)
                health.append((cfg.feed_url, None, len(items)))
            except Exception as exc:
                logger.exception("Podcast collect failed for %s", cfg.feed_url)
                health.append((cfg.feed_url, str(exc), 0))
        return articles, health

    def _collect_feed(self, cfg: PodcastConfig) -> list[dict[str, str]]:
        resp = self._client.get(cfg.feed_url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        show_name = cfg.name or feed.feed.get("title", cfg.feed_url)
        channel_image = self._channel_image(feed)

        items: list[dict[str, str]] = []
        for entry in feed.entries[:_MAX_ENTRIES]:
            url = self._episode_url(entry)
            if not url:
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            content = self._episode_content(entry)
            if not content.strip():
                content = title

            image_url = self._episode_image(entry) or channel_image
            published = self._parse_published(entry)

            items.append(
                {
                    "url": url,
                    "title": title,
                    "content": content,
                    "source": show_name,
                    "category": cfg.category,
                    "content_hash": ContentStore.content_hash(content),
                    "published_at": published,
                    "collected_at": datetime.now(UTC).isoformat(),
                    "image_url": image_url or "",
                    "kind": "podcast",
                },
            )
        return items

    @staticmethod
    def _episode_url(entry: feedparser.FeedParserDict) -> str | None:
        """Return the episode page link, falling back to the enclosure URL."""
        link = entry.get("link", "").strip()
        if link:
            return link
        enclosures = entry.get("enclosures") or []
        if enclosures:
            return enclosures[0].get("href", "").strip() or None
        return None

    @staticmethod
    def _episode_content(entry: feedparser.FeedParserDict) -> str:
        """Extract show notes as plain text (up to 8 000 chars)."""
        # feedparser maps <itunes:summary> to entry.itunes_summary
        itunes_summary = entry.get("itunes_summary", "")
        if itunes_summary:
            return _strip_html(str(itunes_summary))[:8000]

        # content list (Atom-style)
        content_list = entry.get("content")
        if isinstance(content_list, list) and content_list:
            raw = str(content_list[0].get("value") or "")
            if raw.strip():
                return _strip_html(raw)[:8000]

        summary = str(entry.get("summary") or "")
        return _strip_html(summary)[:8000]

    @staticmethod
    def _episode_image(entry: feedparser.FeedParserDict) -> str | None:
        """Return the episode-level artwork URL if present."""
        img = entry.get("itunes_image")
        if isinstance(img, dict):
            return img.get("href") or None
        if isinstance(img, str):
            return img or None
        return None

    @staticmethod
    def _channel_image(feed: feedparser.FeedParserDict) -> str | None:
        """Return the channel-level artwork URL."""
        img = feed.feed.get("itunes_image")
        if isinstance(img, dict):
            return img.get("href") or None
        if isinstance(img, str):
            return img or None
        channel_img = feed.feed.get("image")
        if isinstance(channel_img, dict):
            return channel_img.get("href") or None
        return None

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
        if entry.get("updated_parsed"):
            t = entry.updated_parsed
            return datetime(*t[:6], tzinfo=UTC).isoformat()
        return datetime.now(UTC).isoformat()
