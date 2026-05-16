"""SQLite storage for articles, digests, and ratings."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlite_utils
from sqlite_utils.db import NotFoundError


class ContentStore:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            from condenseit.config import get_data_dir

            db_path = get_data_dir() / "condenseit.db"
        self.db_path = db_path
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db = sqlite_utils.Database(conn)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        if "articles" not in self.db.table_names():
            self.db["articles"].create(
                {
                    "url": str,
                    "title": str,
                    "content": str,
                    "source": str,
                    "category": str,
                    "content_hash": str,
                    "published_at": str,
                    "collected_at": str,
                },
                pk="url",
            )
        if "digests" not in self.db.table_names():
            self.db["digests"].create(
                {
                    "id": int,
                    "created_at": str,
                    "markdown": str,
                    "html": str,
                    "stats_json": str,
                },
                pk="id",
            )
        if "ratings" not in self.db.table_names():
            self.db["ratings"].create(
                {
                    "url": str,
                    "rating": int,
                    "rated_at": str,
                },
                pk="url",
            )
        if "page_snapshots" not in self.db.table_names():
            self.db["page_snapshots"].create(
                {
                    "url": str,
                    "content": str,
                    "content_hash": str,
                    "updated_at": str,
                },
                pk="url",
            )
        if "spending" not in self.db.table_names():
            self.db["spending"].create(
                {
                    "id": int,
                    "amount_usd": float,
                    "model": str,
                    "tokens": int,
                    "recorded_at": str,
                },
                pk="id",
            )
        if "api_keys" not in self.db.table_names():
            self.db["api_keys"].create(
                {
                    "service": str,
                    "key_name": str,
                    "encrypted_value": str,
                    "key_preview": str,
                    "updated_at": str,
                },
                pk="service",
            )
        if "settings" not in self.db.table_names():
            self.db["settings"].create(
                {"key": str, "value": str},
                pk="key",
            )
        if "processed_videos" not in self.db.table_names():
            self.db["processed_videos"].create(
                {"video_id": str, "processed_at": str},
                pk="video_id",
            )
        if "read_articles" not in self.db.table_names():
            self.db["read_articles"].create(
                {
                    "url": str,
                    "read_at": str,
                },
                pk="url",
            )

    def get_setting(self, key: str, default: str = "") -> str:
        if "settings" not in self.db.table_names():
            return default
        try:
            return str(self.db["settings"].get(key)["value"])
        except NotFoundError:
            return default

    def set_setting(self, key: str, value: str) -> None:
        self.db["settings"].upsert({"key": key, "value": value}, pk="key")

    def rating_count(self) -> int:
        if "ratings" not in self.db.table_names():
            return 0
        return self.db["ratings"].count

    @staticmethod
    def content_hash(content: str) -> str:
        normalized = " ".join(content.split()).lower()
        return hashlib.sha256(normalized.encode()).hexdigest()

    def has_article(self, url: str) -> bool:
        try:
            self.db["articles"].get(url)
            return True
        except NotFoundError:
            return False

    def save_article(self, article: dict[str, Any]) -> None:
        self.db["articles"].upsert(article, pk="url")

    def _refresh_article_collection_meta(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        """Update last-seen time and labels when the same URL reappears unchanged.

        Keeps stored body and hash so we do not treat the row as new for the
        digest pipeline, but ``collected_at`` moves forward so UIs such as
        ``/rate`` (ORDER BY collected_at) reflect recent runs.
        """
        row = dict(existing)
        row["collected_at"] = incoming.get(
            "collected_at",
            datetime.now(UTC).isoformat(),
        )
        row["title"] = str(incoming.get("title", row.get("title", "")))
        row["source"] = str(incoming.get("source", row.get("source", "")))
        row["category"] = str(incoming.get("category", row.get("category", "")))
        row["published_at"] = str(
            incoming.get("published_at", row.get("published_at", "")),
        )
        self.save_article(row)

    def articles_collected_since(self, cutoff: datetime) -> list[dict[str, Any]]:
        """Return all articles whose ``collected_at`` is at or after ``cutoff``.

        Used by the pipeline to accumulate same-day articles across multiple
        runs instead of shrinking the pool to only net-new items.
        """
        cutoff_str = cutoff.isoformat()
        return list(
            self.db.query(
                "SELECT * FROM articles WHERE collected_at >= ?"
                " ORDER BY collected_at DESC",
                [cutoff_str],
            ),
        )

    def deduplicate(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fresh: list[dict[str, Any]] = []
        for article in articles:
            url = article["url"]
            content_hash = article.get("content_hash", "")
            if self.has_article(url):
                existing = self.db["articles"].get(url)
                if existing and existing["content_hash"] == content_hash:
                    self._refresh_article_collection_meta(dict(existing), article)
                    continue
            self.save_article(article)
            fresh.append(article)
        return fresh

    def save_digest(
        self,
        markdown: str,
        html: str,
        stats_json: str,
    ) -> int:
        row = {
            "created_at": datetime.now(UTC).isoformat(),
            "markdown": markdown,
            "html": html,
            "stats_json": stats_json,
        }
        self.db["digests"].insert(row)
        return int(self.db.execute("SELECT last_insert_rowid()").fetchone()[0])

    def latest_digest(self) -> dict[str, Any] | None:
        rows = list(
            self.db.query(
                "SELECT * FROM digests ORDER BY id DESC LIMIT 1",
            ),
        )
        return rows[0] if rows else None

    def list_digests(self, limit: int = 20) -> list[dict[str, Any]]:
        return list(
            self.db.query(
                "SELECT id, created_at, stats_json FROM digests "
                "ORDER BY id DESC LIMIT ?",
                [limit],
            ),
        )

    def rate_article(self, url: str, rating: int) -> None:
        self.db["ratings"].upsert(
            {
                "url": url,
                "rating": rating,
                "rated_at": datetime.now(UTC).isoformat(),
            },
            pk="url",
        )

    def import_ratings_pairs(self, pairs: list[tuple[str, int]]) -> int:
        """Upsert many (url, rating) rows. Skips invalid entries. Returns count."""
        applied = 0
        for url, rating in pairs:
            if not url or rating < 1 or rating > 5:
                continue
            self.rate_article(url, int(rating))
            applied += 1
        return applied

    def get_snapshot(self, url: str) -> dict[str, Any] | None:
        try:
            return dict(self.db["page_snapshots"].get(url))
        except NotFoundError:
            return None

    def save_snapshot(self, url: str, content: str) -> None:
        self.db["page_snapshots"].upsert(
            {
                "url": url,
                "content": content,
                "content_hash": self.content_hash(content),
                "updated_at": datetime.now(UTC).isoformat(),
            },
            pk="url",
        )

    def mark_article_read(self, url: str) -> None:
        """Record that the user has read the article at ``url``."""
        self.db["read_articles"].upsert(
            {
                "url": url,
                "read_at": datetime.now(UTC).isoformat(),
            },
            pk="url",
        )

    def mark_article_unread(self, url: str) -> None:
        """Remove ``url`` from the read set so it can appear in future digests."""
        try:
            self.db["read_articles"].delete(url)
        except NotFoundError:
            pass

    def get_read_urls(self) -> set[str]:
        """Return the set of all URLs the user has marked as read."""
        if "read_articles" not in self.db.table_names():
            return set()
        return {str(row["url"]) for row in self.db["read_articles"].rows}
