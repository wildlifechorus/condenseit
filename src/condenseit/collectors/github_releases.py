"""GitHub Releases collector via the public Atom feed.

Every public GitHub repository exposes a releases Atom feed at
``https://github.com/{owner}/{repo}/releases.atom``. No authentication
or API key is required for public repositories.
"""

import logging
from datetime import UTC, datetime

import feedparser
import httpx

from condenseit.collectors.feed_dates import parse_feed_entry_date
from condenseit.collectors.health import collect_with_health
from condenseit.config import GitHubReleasesConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 10


class GitHubReleasesCollector:
    """Collect release notes from GitHub repository Atom feeds."""

    def __init__(self, sources: list[GitHubReleasesConfig]) -> None:
        self.sources = sources
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=digest_fetch_headers(),
        )

    def collect_all_with_health(
        self,
    ) -> tuple[list[dict[str, str]], list[tuple[str, str | None, int]]]:
        """Return ``(articles, [(atom_url, error_or_none, item_count), ...])``."""
        articles: list[dict[str, str]] = []
        health: list[tuple[str, str | None, int]] = []
        for cfg in self.sources:
            atom_url = f"https://github.com/{cfg.repo}/releases.atom"
            items, entry = collect_with_health(
                atom_url,
                lambda cfg=cfg, atom_url=atom_url: self._collect_repo(cfg, atom_url),
                log_label=f"GitHub Releases collect failed for {cfg.repo}",
            )
            articles.extend(items)
            health.append(entry)
        return articles, health

    def _collect_repo(
        self,
        cfg: GitHubReleasesConfig,
        atom_url: str,
    ) -> list[dict[str, str]]:
        resp = self._client.get(atom_url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        items: list[dict[str, str]] = []
        for entry in feed.entries[:_MAX_ENTRIES]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            if not title or not link:
                continue

            # Release notes live in the entry content or summary.
            content = self._entry_content(entry)
            if not content.strip():
                content = title

            published = self._parse_published(entry)
            items.append(
                {
                    "url": link,
                    "title": f"{cfg.repo}: {title}",
                    "content": content,
                    "source": f"GitHub: {cfg.repo}",
                    "category": cfg.category,
                    "content_hash": ContentStore.content_hash(content),
                    "published_at": published,
                    "collected_at": datetime.now(UTC).isoformat(),
                },
            )
        return items

    @staticmethod
    def _entry_content(entry: feedparser.FeedParserDict) -> str:
        """Extract plain-text release notes from an Atom entry."""
        import html
        import re

        raw = ""
        content_list = entry.get("content")
        if isinstance(content_list, list) and content_list:
            raw = str(content_list[0].get("value") or "")
        if not raw.strip():
            raw = str(entry.get("summary") or "")
        if not raw.strip():
            return ""
        # Strip HTML tags for a plain-text representation.
        plain = re.sub(r"<[^>]+>", " ", raw)
        plain = html.unescape(plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        return plain[:8000]

    @staticmethod
    def _parse_published(entry: feedparser.FeedParserDict) -> str:
        return parse_feed_entry_date(entry)
