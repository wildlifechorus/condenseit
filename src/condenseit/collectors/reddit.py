"""Reddit collector via the public subreddit JSON endpoint.

Reddit's public ``.json`` endpoint is accessible without authentication for
public subreddits. No API key is needed. Reddit requires a non-empty
``User-Agent``, which is already provided by ``digest_fetch_headers()``.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from condenseit.api_urls import REDDIT_WEB_BASE
from condenseit.collectors.article_text import fetch_article_text
from condenseit.collectors.feed_dates import unix_timestamp_to_iso
from condenseit.collectors.health import collect_with_health
from condenseit.config import RedditConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

_VALID_SORTS = frozenset({"hot", "new", "top", "rising"})
_VALID_TIME_FILTERS = frozenset({"hour", "day", "week", "month", "year", "all"})


class RedditCollector:
    """Collect posts from public subreddits."""

    def __init__(self, sources: list[RedditConfig]) -> None:
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
            feed_url = self._feed_url(cfg)
            items, entry = collect_with_health(
                feed_url,
                lambda cfg=cfg, feed_url=feed_url: self._collect_subreddit(
                    cfg, feed_url
                ),
                log_label=f"Reddit collect failed for r/{cfg.subreddit}",
            )
            articles.extend(items)
            health.append(entry)
        return articles, health

    @staticmethod
    def _feed_url(cfg: RedditConfig) -> str:
        sort = cfg.sort if cfg.sort in _VALID_SORTS else "hot"
        tf = cfg.time_filter if cfg.time_filter in _VALID_TIME_FILTERS else "day"
        limit = min(cfg.max_items * 2, 100)
        return (
            f"https://www.reddit.com/r/{cfg.subreddit}/{sort}.json"
            f"?t={tf}&limit={limit}&raw_json=1"
        )

    def _collect_subreddit(
        self,
        cfg: RedditConfig,
        feed_url: str,
    ) -> list[dict[str, str]]:
        resp = self._client.get(feed_url)
        resp.raise_for_status()
        data = resp.json()
        data_root = data.get("data")
        if not isinstance(data_root, dict):
            return []
        children_raw = data_root.get("children", [])
        children: list[Any] = children_raw if isinstance(children_raw, list) else []

        items: list[dict[str, str]] = []
        for child in children:
            if len(items) >= cfg.max_items:
                break
            post: dict[str, Any] = child.get("data", {})
            score = int(post.get("score") or 0)
            if score < cfg.min_score:
                continue
            title = post.get("title", "").strip()
            if not title:
                continue

            is_self = bool(post.get("is_self"))
            url = post.get("url", "")
            permalink = REDDIT_WEB_BASE + post.get("permalink", "")

            if is_self:
                # Self post - use body text if available.
                content = (post.get("selftext") or title).strip()
            else:
                content = self._extract_content(url)

            if not content.strip():
                continue

            published = self._ts_to_iso(post.get("created_utc"))
            items.append(
                {
                    "url": url if not is_self else permalink,
                    "title": title,
                    "content": content,
                    "source": f"r/{cfg.subreddit}",
                    "category": cfg.category,
                    "content_hash": ContentStore.content_hash(content),
                    "published_at": published,
                    "collected_at": datetime.now(UTC).isoformat(),
                },
            )
        return items

    def _extract_content(self, url: str) -> str:
        if not url or url.startswith(REDDIT_WEB_BASE):
            return ""
        return fetch_article_text(self._client, url) or ""

    @staticmethod
    def _ts_to_iso(ts: Any) -> str:
        return unix_timestamp_to_iso(ts, use_float=True)
