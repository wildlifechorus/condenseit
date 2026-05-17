"""Source registry (RSS, YouTube, website, and extended types) in SQLite."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from condenseit.config import (
    AppConfig,
    FeedConfig,
    GitHubReleasesConfig,
    GoogleNewsSearchConfig,
    HackerNewsConfig,
    RedditConfig,
    WatchUrlConfig,
    YouTubeChannelConfig,
)
from condenseit.store.database import ContentStore


class SourceRegistry:
    def __init__(self, store: ContentStore) -> None:
        self.store = store
        self._ensure()

    def _ensure(self) -> None:
        if "sources" not in self.store.db.table_names():
            self.store.db["sources"].create(
                {
                    "id": int,
                    "type": str,
                    "name": str,
                    "url": str,
                    "category": str,
                    "priority": int,
                    "enabled": int,
                    "extra_json": str,
                    "created_at": str,
                    "last_checked_at": str,
                    "last_status": str,
                    "last_error": str,
                    "last_item_count": int,
                },
                pk="id",
            )
        else:
            self._ensure_source_health_columns()

    def _ensure_source_health_columns(self) -> None:
        rows = list(self.store.db.execute("PRAGMA table_info(sources)"))
        names = {r[1] for r in rows}
        alters: list[tuple[str, str]] = [
            ("last_checked_at", "ALTER TABLE sources ADD COLUMN last_checked_at TEXT"),
            ("last_status", "ALTER TABLE sources ADD COLUMN last_status TEXT"),
            ("last_error", "ALTER TABLE sources ADD COLUMN last_error TEXT"),
            (
                "last_item_count",
                "ALTER TABLE sources ADD COLUMN last_item_count INTEGER",
            ),
        ]
        for col, sql in alters:
            if col not in names:
                self.store.db.execute(sql)

    def record_health(
        self,
        url: str,
        *,
        status: str,
        error: str | None = None,
        item_count: int | None = None,
    ) -> None:
        """Update last fetch health for a source row matching ``url``."""
        now = datetime.now(UTC).isoformat()
        err = (error or "")[:2000]
        count = -1 if item_count is None else int(item_count)
        self.store.db.execute(
            """
            UPDATE sources SET
              last_checked_at = ?,
              last_status = ?,
              last_error = ?,
              last_item_count = ?
            WHERE url = ?
            """,
            [now, status, err, count, url],
        )

    def seed_from_config(self, config: AppConfig) -> None:
        existing_urls = {row["url"] for row in self.store.db["sources"].rows}

        def _add_if_new(*args: Any, **kwargs: Any) -> None:
            url = kwargs.get("url") if "url" in kwargs else args[4]
            if url in existing_urls:
                return
            self.add(*args, **kwargs)
            existing_urls.add(url)

        for feed in config.feeds:
            _add_if_new("rss", feed.url, feed.category, feed.priority, feed.url)
        for ch in config.youtube_channels:
            rss = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch.channel_id}"
            _add_if_new(
                "youtube",
                ch.handle or ch.channel_id,
                ch.category,
                2,
                rss,
                extra={"channel_id": ch.channel_id, "handle": ch.handle},
            )
        for watch in config.watch_urls:
            _add_if_new(
                "website",
                watch.url,
                watch.category,
                2,
                watch.url,
                extra={
                    "selector": watch.selector,
                    "change_threshold": watch.change_threshold,
                },
            )

    def add(
        self,
        source_type: str,
        name: str,
        category: str,
        priority: int,
        url: str,
        *,
        enabled: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> int:
        row = {
            "type": source_type,
            "name": name,
            "url": url,
            "category": category,
            "priority": priority,
            "enabled": 1 if enabled else 0,
            "extra_json": json.dumps(extra or {}),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.store.db["sources"].insert(row)
        return int(self.store.db.execute("SELECT last_insert_rowid()").fetchone()[0])

    def list_enabled(self) -> list[dict[str, Any]]:
        rows = self.store.db.query(
            "SELECT * FROM sources WHERE enabled = 1 ORDER BY priority, id",
        )
        return [dict(r) for r in rows]

    def list_all(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.store.db["sources"].rows]

    def delete(self, source_id: int) -> None:
        self.store.db["sources"].delete(source_id)

    def toggle(self, source_id: int, enabled: bool) -> None:
        self.store.db["sources"].update(source_id, {"enabled": 1 if enabled else 0})

    def update(
        self,
        source_id: int,
        source_type: str,
        name: str,
        category: str,
        priority: int,
        url: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Update source configuration and clear stale fetch health."""
        self.store.db["sources"].update(
            source_id,
            {
                "type": source_type,
                "name": name,
                "url": url,
                "category": category,
                "priority": priority,
                "extra_json": json.dumps(extra or {}),
                "last_checked_at": "",
                "last_status": "",
                "last_error": "",
                "last_item_count": -1,
            },
        )

    def feeds_for_config(self) -> list[FeedConfig]:
        return [
            FeedConfig(
                url=r["url"],
                category=r["category"],
                priority=int(r["priority"]),
            )
            for r in self.list_enabled()
            if r["type"] == "rss"
        ]

    def youtube_for_config(self) -> list[YouTubeChannelConfig]:
        out: list[YouTubeChannelConfig] = []
        for r in self.list_enabled():
            if r["type"] != "youtube":
                continue
            extra = json.loads(r.get("extra_json") or "{}")
            out.append(
                YouTubeChannelConfig(
                    handle=extra.get("handle", ""),
                    channel_id=extra.get("channel_id", ""),
                    category=r["category"],
                ),
            )
        return out

    def watch_for_config(self) -> list[WatchUrlConfig]:
        out: list[WatchUrlConfig] = []
        for r in self.list_enabled():
            if r["type"] != "website":
                continue
            extra = json.loads(r.get("extra_json") or "{}")
            out.append(
                WatchUrlConfig(
                    url=r["url"],
                    category=r["category"],
                    selector=extra.get("selector"),
                    change_threshold=float(extra.get("change_threshold", 0.05)),
                ),
            )
        return out

    def google_news_for_config(self) -> list[GoogleNewsSearchConfig]:
        out: list[GoogleNewsSearchConfig] = []
        for r in self.list_enabled():
            if r["type"] != "google_news":
                continue
            extra = json.loads(r.get("extra_json") or "{}")
            out.append(
                GoogleNewsSearchConfig(
                    query=extra.get("query", ""),
                    language=extra.get("language", "en"),
                    country=extra.get("country", "US"),
                    category=r["category"],
                    priority=int(r["priority"]),
                ),
            )
        return out

    def hackernews_for_config(self) -> list[HackerNewsConfig]:
        out: list[HackerNewsConfig] = []
        for r in self.list_enabled():
            if r["type"] != "hackernews":
                continue
            extra = json.loads(r.get("extra_json") or "{}")
            out.append(
                HackerNewsConfig(
                    feed=extra.get("feed", "top"),
                    max_items=int(extra.get("max_items", 20)),
                    min_score=int(extra.get("min_score", 50)),
                    category=r["category"],
                    priority=int(r["priority"]),
                ),
            )
        return out

    def reddit_for_config(self) -> list[RedditConfig]:
        out: list[RedditConfig] = []
        for r in self.list_enabled():
            if r["type"] != "reddit":
                continue
            extra = json.loads(r.get("extra_json") or "{}")
            out.append(
                RedditConfig(
                    subreddit=extra.get("subreddit", r["name"]),
                    sort=extra.get("sort", "hot"),
                    time_filter=extra.get("time_filter", "day"),
                    max_items=int(extra.get("max_items", 20)),
                    min_score=int(extra.get("min_score", 10)),
                    category=r["category"],
                    priority=int(r["priority"]),
                ),
            )
        return out

    def github_releases_for_config(self) -> list[GitHubReleasesConfig]:
        out: list[GitHubReleasesConfig] = []
        for r in self.list_enabled():
            if r["type"] != "github_releases":
                continue
            extra = json.loads(r.get("extra_json") or "{}")
            out.append(
                GitHubReleasesConfig(
                    repo=extra.get("repo", ""),
                    category=r["category"],
                    priority=int(r["priority"]),
                ),
            )
        return out
