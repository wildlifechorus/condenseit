"""Tests for the Atom feed output endpoint and feed token management."""

from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from condenseit.store.database import ContentStore
from condenseit.web.app import create_app

_AUTH = {"Authorization": "Bearer condenseit"}
_ATOM_NS = "http://www.w3.org/2005/Atom"

_SAMPLE_ITEMS = [
    {
        "id": 0,
        "title": "AI Safety Update",
        "url": "https://example.com/ai-safety",
        "summary": "A summary of recent AI safety developments.",
        "tldr": "Quick take on AI safety.",
        "key_takeaways": ["Point one", "Point two"],
        "source": "Example Feed",
        "category": "AI",
        "published_at": "2026-05-27T08:00:00+00:00",
        "kind": "article",
        "topics": ["AI", "safety"],
    },
    {
        "id": 1,
        "title": "Open Source News",
        "url": "https://example.com/oss",
        "summary": "Open source project roundup.",
        "tldr": "",
        "key_takeaways": [],
        "source": "OSS Feed",
        "category": "Technology",
        "published_at": "2026-05-27T09:00:00+00:00",
        "kind": "article",
        "topics": [],
    },
]


def _make_client_with_digest(tmp_path, monkeypatch) -> tuple[TestClient, ContentStore]:
    """Create a test client with a pre-populated digest in the DB."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))
    store = ContentStore()
    payload = {
        "articles_count": len(_SAMPLE_ITEMS),
        "digest_items": _SAMPLE_ITEMS,
    }
    store.save_digest("# Digest", "<p>Digest</p>", json.dumps(payload))
    client = TestClient(create_app())
    return client, store


def _make_client_empty(tmp_path, monkeypatch) -> TestClient:
    """Create a test client with an empty DB (no digests)."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))
    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def test_feed_requires_auth(tmp_path, monkeypatch) -> None:
    """Unauthenticated requests to /api/feed/atom should be rejected."""
    client = _make_client_empty(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom")
    assert resp.status_code == 401


def test_feed_rejects_wrong_token(tmp_path, monkeypatch) -> None:
    """A wrong token should be rejected."""
    client, store = _make_client_with_digest(tmp_path, monkeypatch)
    store.set_setting("feed_token", "correct-token")
    resp = client.get("/api/feed/atom?token=wrong-token")
    assert resp.status_code == 401


def test_feed_rejects_empty_token_when_feed_token_set(tmp_path, monkeypatch) -> None:
    """An empty token should fail even if a feed token exists."""
    client, store = _make_client_with_digest(tmp_path, monkeypatch)
    store.set_setting("feed_token", "correct-token")
    resp = client.get("/api/feed/atom?token=")
    assert resp.status_code == 401


def test_feed_accepts_correct_token(tmp_path, monkeypatch) -> None:
    """A correct feed token in ?token= should grant access."""
    client, store = _make_client_with_digest(tmp_path, monkeypatch)
    store.set_setting("feed_token", "my-secret-token")
    resp = client.get("/api/feed/atom?token=my-secret-token")
    assert resp.status_code == 200


def test_feed_accepts_bearer_auth(tmp_path, monkeypatch) -> None:
    """The existing Bearer token (admin password) still works for the feed."""
    client = _make_client_empty(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom", headers=_AUTH)
    assert resp.status_code == 200


def test_feed_rejects_revoked_token(tmp_path, monkeypatch) -> None:
    """After revocation, the old token should no longer work."""
    client, store = _make_client_with_digest(tmp_path, monkeypatch)
    store.set_setting("feed_token", "active-token")
    assert client.get("/api/feed/atom?token=active-token").status_code == 200
    # Revoke
    store.set_setting("feed_token", "")
    assert client.get("/api/feed/atom?token=active-token").status_code == 401


# ---------------------------------------------------------------------------
# Atom XML structure
# ---------------------------------------------------------------------------


def test_feed_returns_atom_content_type(tmp_path, monkeypatch) -> None:
    client = _make_client_empty(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom", headers=_AUTH)
    assert resp.status_code == 200
    assert "application/atom+xml" in resp.headers["content-type"]


def test_feed_is_valid_xml(tmp_path, monkeypatch) -> None:
    client = _make_client_empty(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom", headers=_AUTH)
    assert resp.status_code == 200
    # Should not raise
    ET.fromstring(resp.content)


def test_feed_empty_digest_returns_valid_atom(tmp_path, monkeypatch) -> None:
    """With no digests in the DB, an empty but valid Atom feed is returned."""
    client = _make_client_empty(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom", headers=_AUTH)
    assert resp.status_code == 200
    root = ET.fromstring(resp.content)
    assert root.tag == f"{{{_ATOM_NS}}}feed"
    entries = root.findall(f"{{{_ATOM_NS}}}entry")
    assert entries == []
    title = root.findtext(f"{{{_ATOM_NS}}}title")
    assert title == "CondenseIt Digest"


def test_feed_includes_entries_for_digest_items(tmp_path, monkeypatch) -> None:
    """Each digest item should appear as an Atom entry."""
    client, _ = _make_client_with_digest(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom", headers=_AUTH)
    assert resp.status_code == 200
    root = ET.fromstring(resp.content)
    entries = root.findall(f"{{{_ATOM_NS}}}entry")
    assert len(entries) == len(_SAMPLE_ITEMS)


def test_feed_entry_fields(tmp_path, monkeypatch) -> None:
    """The first entry should have correct title, link, id, summary and content."""
    client, _ = _make_client_with_digest(tmp_path, monkeypatch)
    resp = client.get("/api/feed/atom", headers=_AUTH)
    root = ET.fromstring(resp.content)
    entry = root.findall(f"{{{_ATOM_NS}}}entry")[0]

    title = entry.findtext(f"{{{_ATOM_NS}}}title")
    assert title == "AI Safety Update"

    link = entry.find(f"{{{_ATOM_NS}}}link")
    assert link is not None
    assert link.get("href") == "https://example.com/ai-safety"

    entry_id = entry.findtext(f"{{{_ATOM_NS}}}id")
    assert entry_id == "https://example.com/ai-safety"

    summary = entry.findtext(f"{{{_ATOM_NS}}}summary")
    assert summary == "Quick take on AI safety."

    content = entry.find(f"{{{_ATOM_NS}}}content")
    assert content is not None
    assert content.get("type") == "html"
    assert "A summary of recent AI safety" in (content.text or "")
    assert "Point one" in (content.text or "")
    assert "AI" in (content.text or "")

    category = entry.find(f"{{{_ATOM_NS}}}category")
    assert category is not None
    assert category.get("term") == "AI"


# ---------------------------------------------------------------------------
# Feed token admin API
# ---------------------------------------------------------------------------


def test_feed_token_generate_and_retrieve(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))
    client = TestClient(create_app())

    info = client.get("/api/config/feed-token", headers=_AUTH).json()
    assert info["exists"] is False
    assert info["token"] is None
    assert info["feed_url"] is None

    generated = client.post("/api/config/feed-token", headers=_AUTH).json()
    assert generated["exists"] is True
    assert generated["token"] is not None
    assert "/api/feed/atom?token=" in generated["feed_url"]

    info2 = client.get("/api/config/feed-token", headers=_AUTH).json()
    assert info2["token"] == generated["token"]


def test_feed_token_revoke(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))
    client = TestClient(create_app())

    client.post("/api/config/feed-token", headers=_AUTH)

    rev = client.delete("/api/config/feed-token", headers=_AUTH)
    assert rev.status_code == 200
    assert rev.json()["ok"] is True

    info = client.get("/api/config/feed-token", headers=_AUTH).json()
    assert info["exists"] is False


def test_feed_token_generate_replaces_old_token(tmp_path, monkeypatch) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))
    client = TestClient(create_app())

    first = client.post("/api/config/feed-token", headers=_AUTH).json()["token"]
    second = client.post("/api/config/feed-token", headers=_AUTH).json()["token"]
    assert first != second
