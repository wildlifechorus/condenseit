"""PWA export build tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from condenseit.config import AppConfig
from condenseit.pwa.build import build_digest_pwa
from condenseit.store.database import ContentStore


@pytest.fixture(autouse=True)
def skip_vite(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Skip the Vite build during tests so we always exercise the
    Python fallback bundle path (fast, no Node.js required).
    """
    monkeypatch.setenv("CONDENSEIT_SKIP_VITE_BUILD", "1")


def test_pwa_build_writes_files(tmp_path: Path) -> None:
    store = ContentStore(db_path=tmp_path / "t.db")
    cfg = AppConfig()
    cfg.vps.digest_url = "https://digest.example.com"
    out = tmp_path / "pwa"
    info = build_digest_pwa(out, store, cfg)

    # digest-data.json is always written (used by the Vite PWA)
    assert (out / "digest-data.json").is_file()
    assert info["digest_id"] == 0

    data = json.loads((out / "digest-data.json").read_text(encoding="utf-8"))
    assert data["meta"]["id"] == 0
    assert data["items"] == []

    # Fallback HTML bundle
    assert (out / "index.html").is_file()
    assert (out / "manifest.webmanifest").is_file()
    assert (out / "sw.js").is_file()
    assert (out / "pwa-ratings.js").is_file()

    html = (out / "index.html").read_text(encoding="utf-8")
    assert "CondenseIt Digest" in html
    assert "serviceWorker" in html
    assert "pwa-ratings-root" in html
    assert "condenseit-pwa-ratings-cfg" in html


def test_pwa_build_includes_digest_items(tmp_path: Path) -> None:
    store = ContentStore(db_path=tmp_path / "t.db")
    stats = {
        "articles_count": 1,
        "digest_items": [
            {
                "id": 0,
                "title": "T",
                "url": "https://example.com",
                "summary": "Here is a 2-3 sentence summary of the article: S",
                "source": "feed",
                "category": "C",
                "published_at": "",
                "kind": "article",
            },
        ],
    }
    store.save_digest("# x", "<p>x</p>", json.dumps(stats))
    cfg = AppConfig()
    out = tmp_path / "pwa2"
    build_digest_pwa(out, store, cfg)

    data = json.loads((out / "digest-data.json").read_text(encoding="utf-8"))
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["title"] == "T"
    # LLM prefix should be stripped
    assert not item["summary"].startswith("Here is")

    # Fallback HTML should embed the items for the filter widget
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "condenseit-digest-items-data" in html
    assert (out / "digest-filter.js").is_file()

    sw = (out / "sw.js").read_text(encoding="utf-8")
    assert "digest-data.json" in sw
