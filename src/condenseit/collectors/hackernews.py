"""Hacker News collector via the official public Firebase JSON API.

No authentication or API key is required. Rate limiting is handled by
fetching only the item detail pages we intend to use.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import trafilatura

from condenseit.config import HackerNewsConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

_HN_BASE = 'https://hacker-news.firebaseio.com/v0'
_HN_ITEM_URL = 'https://news.ycombinator.com/item?id={id}'
_VALID_FEEDS = frozenset({'top', 'best', 'new', 'ask', 'show'})


class HackerNewsCollector:
    """Collect top/best/new/ask/show stories from Hacker News."""

    def __init__(self, sources: list[HackerNewsConfig]) -> None:
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
            feed = cfg.feed if cfg.feed in _VALID_FEEDS else 'top'
            feed_url = f'{_HN_BASE}/{feed}stories.json'
            try:
                items = self._collect_feed(cfg, feed, feed_url)
                articles.extend(items)
                health.append((feed_url, None, len(items)))
            except Exception as exc:
                logger.exception('HN collect failed for feed %r', feed)
                health.append((feed_url, str(exc), 0))
        return articles, health

    def _collect_feed(
        self,
        cfg: HackerNewsConfig,
        feed: str,
        feed_url: str,
    ) -> list[dict[str, str]]:
        resp = self._client.get(feed_url)
        resp.raise_for_status()
        story_ids: list[int] = resp.json() or []

        items: list[dict[str, str]] = []
        checked = 0

        for story_id in story_ids:
            if len(items) >= cfg.max_items:
                break
            # Fetch enough candidate items to satisfy max_items even after
            # score filtering; bail early if we checked 3x max_items.
            if checked >= cfg.max_items * 3:
                break
            checked += 1

            try:
                item = self._fetch_item(story_id)
            except Exception:
                logger.debug('HN item fetch failed for %d', story_id, exc_info=True)
                continue

            if not item:
                continue
            score = int(item.get('score') or 0)
            if score < cfg.min_score:
                continue
            url = item.get('url', '')
            title = item.get('title', '')
            if not title:
                continue

            if url:
                content = self._extract_content(url)
            else:
                # Self/Ask post - use the text body if available.
                content = item.get('text') or title

            if not content.strip():
                continue

            published = self._ts_to_iso(item.get('time'))
            hn_link = _HN_ITEM_URL.format(id=story_id)
            items.append(
                {
                    'url': url or hn_link,
                    'title': title,
                    'content': content,
                    'source': f'Hacker News ({feed})',
                    'category': cfg.category,
                    'content_hash': ContentStore.content_hash(content),
                    'published_at': published,
                    'collected_at': datetime.now(UTC).isoformat(),
                },
            )
        return items

    def _fetch_item(self, story_id: int) -> dict[str, Any] | None:
        resp = self._client.get(f'{_HN_BASE}/item/{story_id}.json')
        resp.raise_for_status()
        return resp.json()

    def _extract_content(self, url: str) -> str:
        try:
            page = self._client.get(url)
            page.raise_for_status()
            extracted = trafilatura.extract(page.text, include_comments=False)
            if extracted:
                return extracted
        except Exception:
            logger.debug('Article fetch failed for %s', url, exc_info=True)
        return ''

    @staticmethod
    def _ts_to_iso(ts: Any) -> str:
        if ts:
            try:
                return datetime.fromtimestamp(int(ts), tz=UTC).isoformat()
            except (TypeError, ValueError, OSError):
                pass
        return datetime.now(UTC).isoformat()
