#!/usr/bin/env python3
"""Seed additional sources before the next Ollama PWA deploy."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


# The seeder runs as a standalone script, so make local src imports available
# before importing application modules.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from condenseit.config import load_config  # noqa: E402
from condenseit.store.database import ContentStore  # noqa: E402
from condenseit.store.sources import SourceRegistry  # noqa: E402


@dataclass(frozen=True)
class SeedSource:
    """Source metadata inserted into the local source registry."""

    source_type: str
    name: str
    url: str
    category: str
    priority: int


SOURCES: tuple[SeedSource, ...] = (
    SeedSource(
        source_type="rss",
        name="BBC News World",
        url="https://feeds.bbci.co.uk/news/world/rss.xml",
        category="General News",
        priority=2,
    ),
    SeedSource(
        source_type="rss",
        name="Reuters Top News",
        # Reuters no longer exposes a reliable public RSS feed; Google News
        # keeps this live while still filtering for Reuters-hosted reporting.
        url=(
            "https://news.google.com/rss/search?"
            "q=site%3Areuters.com%20Reuters%20when%3A1d"
            "&hl=en-GB&gl=GB&ceid=GB:en"
        ),
        category="General News",
        priority=2,
    ),
    SeedSource(
        source_type="rss",
        name="Kyiv Independent",
        url="https://kyivindependent.com/news-archive/rss/",
        category="Ukraine",
        priority=1,
    ),
    SeedSource(
        source_type="website",
        name="Institute for the Study of War",
        url="https://www.understandingwar.org/newsroom",
        category="Ukraine",
        priority=1,
    ),
    SeedSource(
        source_type="rss",
        name="Hacker News frontpage",
        url="https://hnrss.org/frontpage",
        category="Developer News",
        priority=1,
    ),
)


def main() -> int:
    """Insert requested deploy sources into SQLite, skipping existing URLs."""
    os.chdir(ROOT)
    load_config()
    store = ContentStore()
    registry = SourceRegistry(store)
    existing_urls = {str(row["url"]) for row in registry.list_all()}

    added = 0
    skipped = 0
    for source in SOURCES:
        if source.url in existing_urls:
            skipped += 1
            print(f"skip: {source.name} ({source.url})")
            continue

        registry.add(
            source.source_type,
            source.name,
            source.category,
            source.priority,
            source.url,
        )
        existing_urls.add(source.url)
        added += 1
        print(f"add:  {source.name} ({source.category})")

    print(f"done: added {added}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
