"""SQLite storage for articles, digests, and ratings."""

from __future__ import annotations

import hashlib
import json
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
        # timeout=30 makes SQLite retry for up to 30 s before raising
        # "database is locked". This prevents spurious 500s when the
        # digest background thread and the web server both write
        # concurrently (e.g. /api/dismiss during a running digest).
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
        self.db = sqlite_utils.Database(conn)
        # WAL mode allows concurrent readers alongside a single writer,
        # eliminating the lock contention that causes 500s on write
        # endpoints while the digest pipeline is committing data.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
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
                    "digest_id": int,
                    "digest_run_id": str,
                },
                pk="id",
            )
        else:
            existing_cols = {
                row[1]
                for row in self.db.execute(
                    "PRAGMA table_info(spending)"
                ).fetchall()
            }
            if "digest_id" not in existing_cols:
                self.db.execute(
                    "ALTER TABLE spending ADD COLUMN digest_id INTEGER"
                )
            if "digest_run_id" not in existing_cols:
                self.db.execute(
                    "ALTER TABLE spending ADD COLUMN digest_run_id TEXT"
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
                    "title": str,
                },
                pk="url",
            )
        else:
            # Migration: add title column to existing read_articles tables.
            existing_cols = {
                row[1]
                for row in self.db.execute(
                    "PRAGMA table_info(read_articles)"
                ).fetchall()
            }
            if "title" not in existing_cols:
                self.db.execute(
                    "ALTER TABLE read_articles ADD COLUMN title TEXT"
                )
        if "digest_run_logs" not in self.db.table_names():
            self.db["digest_run_logs"].create(
                {
                    "id": int,
                    "digest_id": int,
                    "log_text": str,
                    "created_at": str,
                },
                pk="id",
            )
        if "read_later" not in self.db.table_names():
            self.db["read_later"].create(
                {
                    "url": str,
                    "title": str,
                    "summary": str,
                    "tldr": str,
                    "key_takeaways": str,
                    "source": str,
                    "category": str,
                    "kind": str,
                    "published_at": str,
                    "saved_at": str,
                },
                pk="url",
            )
        if "dismissed_articles" not in self.db.table_names():
            self.db["dismissed_articles"].create(
                {
                    "url": str,
                    "title": str,
                    "dismissed_at": str,
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

    def get_article(self, url: str) -> dict[str, Any] | None:
        """Return the stored article row for ``url``, or ``None`` if not found."""
        try:
            return dict(self.db["articles"].get(url))
        except NotFoundError:
            return None

    def save_article(self, article: dict[str, Any]) -> None:
        self.db["articles"].upsert(article, pk="url")

    def _refresh_article_collection_meta(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
    ) -> None:
        """Update mutable labels when the same URL reappears unchanged.

        ``collected_at`` is intentionally NOT updated here. It retains the
        timestamp of the first time this article was collected, which keeps
        ``articles_collected_since(today_midnight)`` scoped to articles that
        are genuinely new today. Refreshing ``collected_at`` caused articles
        from previous days to re-enter the same-day pool on every pipeline
        run as long as the article was still present in the RSS feed.
        """
        row = dict(existing)
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

    def update_digest_stats(self, digest_id: int, stats_json: str) -> None:
        self.db.execute(
            "UPDATE digests SET stats_json = ? WHERE id = ?",
            [stats_json, digest_id],
        )

    def attach_spending_to_digest(
        self,
        digest_run_id: str,
        digest_id: int,
    ) -> None:
        """Associate OpenRouter spend rows from one pipeline run with a digest."""
        if not digest_run_id:
            return
        self.db.execute(
            "UPDATE spending SET digest_id = ? WHERE digest_run_id = ?",
            [digest_id, digest_run_id],
        )

    def sum_spending_for_digest(self, digest_id: int) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(amount_usd), 0) FROM spending WHERE digest_id = ?",
            [digest_id],
        ).fetchone()
        return float(row[0] or 0)

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

    def dismiss_article(self, url: str, title: str | None = None) -> None:
        """Record that the user dismissed ``url`` (not interested, no read intent).

        Also marks the article as read so it is excluded from future digests.
        The dismiss signal is stored separately so the ranking engine can treat
        it as a mild negative implicit signal, distinct from an explicit low
        star rating.
        """
        row: dict[str, Any] = {
            "url": url,
            "dismissed_at": datetime.now(UTC).isoformat(),
        }
        if title:
            row["title"] = title.strip()
        else:
            row["title"] = ""
        self.db["dismissed_articles"].upsert(row, pk="url")
        # Also mark as read so the pipeline excludes it from future digests.
        self.mark_article_read(url, title=title)

    def get_dismissed_urls(self) -> set[str]:
        """Return the set of all URLs the user has dismissed."""
        if "dismissed_articles" not in self.db.table_names():
            return set()
        return {str(row["url"]) for row in self.db["dismissed_articles"].rows}

    def dismissed_count(self) -> int:
        """Return the total number of dismissed articles."""
        if "dismissed_articles" not in self.db.table_names():
            return 0
        return self.db["dismissed_articles"].count

    def mark_article_read(self, url: str, title: str | None = None) -> None:
        """Record that the user has read the article at ``url``.

        ``title`` is stored so the pipeline can also exclude re-appeared
        articles that share the same title but arrive with a different URL
        (e.g. Google News opaque redirect URLs that rotate between fetches).
        """
        row: dict[str, Any] = {
            "url": url,
            "read_at": datetime.now(UTC).isoformat(),
        }
        if title:
            row["title"] = title.strip()
        self.db["read_articles"].upsert(row, pk="url")

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

    def get_read_titles(self) -> set[str]:
        """Return lowercased titles of all articles the user has marked as read.

        Only rows that have a non-empty ``title`` are included. Used by the
        pipeline to exclude re-appeared articles that share the same title but
        arrive under a different URL (e.g. rotating Google News redirect URLs).
        """
        if "read_articles" not in self.db.table_names():
            return set()
        return {
            str(row["title"]).lower().strip()
            for row in self.db["read_articles"].rows
            if row.get("title")
        }

    def save_read_later(self, item: dict[str, Any]) -> None:
        """Persist a digest item to the read-later list.

        ``key_takeaways`` is stored as a JSON array string so it survives a
        round-trip through SQLite without a schema change.
        """
        key_takeaways = item.get("key_takeaways") or []
        if isinstance(key_takeaways, list):
            key_takeaways = json.dumps(key_takeaways)
        self.db["read_later"].upsert(
            {
                "url": str(item.get("url", "")).strip(),
                "title": str(item.get("title", "")),
                "summary": str(item.get("summary", "")),
                "tldr": str(item.get("tldr", "") or ""),
                "key_takeaways": str(key_takeaways),
                "source": str(item.get("source", "")),
                "category": str(item.get("category", "")),
                "kind": str(item.get("kind", "article")),
                "published_at": str(item.get("published_at", "") or ""),
                "saved_at": datetime.now(UTC).isoformat(),
            },
            pk="url",
        )

    def remove_read_later(self, url: str) -> None:
        """Remove a URL from the read-later list."""
        try:
            self.db["read_later"].delete(url)
        except NotFoundError:
            pass

    def get_read_later_urls(self) -> set[str]:
        """Return the set of all URLs currently saved for later."""
        if "read_later" not in self.db.table_names():
            return set()
        return {str(row["url"]) for row in self.db["read_later"].rows}

    def list_read_later(self) -> list[dict[str, Any]]:
        """Return all read-later items ordered newest-saved first.

        ``key_takeaways`` is deserialized back to a list before returning.
        """
        if "read_later" not in self.db.table_names():
            return []
        rows = list(
            self.db.query(
                "SELECT * FROM read_later ORDER BY saved_at DESC",
            )
        )
        for row in rows:
            raw_kt = row.get("key_takeaways") or "[]"
            try:
                row["key_takeaways"] = json.loads(raw_kt)
            except (json.JSONDecodeError, TypeError):
                row["key_takeaways"] = []
        return rows

    def save_run_log(self, digest_id: int | None, log_text: str) -> int:
        """Persist the captured log from a digest run."""
        row = {
            "digest_id": digest_id,
            "log_text": log_text,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.db["digest_run_logs"].insert(row)
        return int(self.db.execute("SELECT last_insert_rowid()").fetchone()[0])

    def list_run_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent run log summaries (no full text)."""
        return list(
            self.db.query(
                "SELECT id, digest_id, created_at,"
                " substr(log_text, 1, 200) AS log_preview"
                " FROM digest_run_logs ORDER BY id DESC LIMIT ?",
                [limit],
            )
        )

    def get_run_log(self, log_id: int) -> dict[str, Any] | None:
        """Return a single run log by id."""
        rows = list(
            self.db.query(
                "SELECT * FROM digest_run_logs WHERE id = ?",
                [log_id],
            )
        )
        return dict(rows[0]) if rows else None

    def latest_run_log(self) -> dict[str, Any] | None:
        """Return the most recent run log."""
        rows = list(
            self.db.query(
                "SELECT * FROM digest_run_logs ORDER BY id DESC LIMIT 1",
            )
        )
        return dict(rows[0]) if rows else None
