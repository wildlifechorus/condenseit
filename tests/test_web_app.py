from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from condenseit.store.database import ContentStore
from condenseit.web.app import _digest_cost_usd, create_app

# All API routes now require auth. Use the built-in default password via Bearer token.
_AUTH = {"Authorization": "Bearer condenseit"}


def test_health_and_api_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Core JSON API and health endpoints return expected shapes."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    health = client.get("/health")
    assert health.json() == {"status": "ok"}

    status = client.get("/api/digest/status", headers=_AUTH)
    assert status.json()["state"] == "idle"

    # Digest list and latest (empty DB)
    digests = client.get("/api/digests", headers=_AUTH)
    assert digests.status_code == 200
    assert digests.json() == []

    latest = client.get("/api/digests/latest", headers=_AUTH)
    assert latest.status_code == 200
    assert latest.json() is None


def test_spa_shell_served_for_ui_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Pages served as SPA shell when frontend/dist is present."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())
    home = client.get("/")
    assert home.status_code == 200
    assert "CondenseIt" in home.text

    admin = client.get("/admin/")
    assert admin.status_code == 200
    assert "Admin" in admin.text


def test_spa_uses_condenseit_frontend_dist_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Explicit ``CONDENSEIT_FRONTEND_DIST`` is used (Docker layout)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!DOCTYPE html><html><title>CondenseIt</title>override-marker</html>",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CONDENSEIT_FRONTEND_DIST", str(dist))
    client = TestClient(create_app())
    home = client.get("/")
    assert home.status_code == 200
    assert "override-marker" in home.text


def test_sources_api_updates_source_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The source update endpoint persists editable source fields."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    added = client.post(
        "/api/sources",
        headers=_AUTH,
        json={
            "source_type": "rss",
            "name": "Old Feed",
            "url": "https://example.com/old.xml",
            "category": "Old",
            "priority": 2,
        },
    )
    assert added.status_code == 200

    sources = client.get("/api/sources", headers=_AUTH).json()
    source_id = next(s["id"] for s in sources if s["name"] == "Old Feed")

    updated = client.put(
        f"/api/sources/{source_id}",
        headers=_AUTH,
        json={
            "source_type": "google_news",
            "name": "AI News",
            "query": "AI safety",
            "language": "en",
            "country": "GB",
            "category": "Research",
            "priority": 1,
        },
    )
    assert updated.status_code == 200

    rows = client.get("/api/sources", headers=_AUTH).json()
    row = next(s for s in rows if s["id"] == source_id)
    extra = json.loads(row["extra_json"])
    assert row["type"] == "google_news"
    assert row["name"] == "AI News"
    assert row["category"] == "Research"
    assert row["priority"] == 1
    assert "AI+safety" in row["url"]
    assert extra == {"query": "AI safety", "language": "en", "country": "GB"}


def test_digest_api_returns_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The /api/digests/latest endpoint returns structured items."""
    data_root = tmp_path / "appdata"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))

    store = ContentStore()
    payload = {
        "articles_count": 1,
        "digest_items": [
            {
                "id": 0,
                "title": "Hello",
                "url": "https://example.com/a",
                "summary": (
                    "Here is a 2-3 sentence summary of the article: Summary text."
                ),
                "source": "Example Feed",
                "category": "News",
                "published_at": "2026-01-15T12:00:00+00:00",
                "kind": "article",
            },
        ],
    }
    store.save_digest("# Hello", "<p>Hello</p>", json.dumps(payload))
    client = TestClient(create_app())

    latest = client.get("/api/digests/latest", headers=_AUTH)
    assert latest.status_code == 200
    data = latest.json()
    assert data is not None
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["title"] == "Hello"
    # Summary should have LLM prefix stripped
    assert not item["summary"].startswith("Here is")
    assert "Summary text" in item["summary"]


def test_digest_cost_uses_explicit_spending_link(tmp_path) -> None:
    """Digest-linked spend rows should be preferred over timestamp inference."""
    store = ContentStore(db_path=tmp_path / "test.db")
    digest_id = store.save_digest(
        "# Costed",
        "<p>Costed</p>",
        json.dumps({"articles_count": 1}),
    )
    store.db["spending"].insert(
        {
            "amount_usd": 0.1234,
            "model": "openrouter/test",
            "tokens": 100,
            "recorded_at": "2026-05-17T07:00:00+00:00",
            "digest_id": digest_id,
            "digest_run_id": "run-1",
        },
    )

    cost = _digest_cost_usd(
        store,
        digest_id,
        "2026-05-17T07:05:00+00:00",
        {},
    )

    assert cost == pytest.approx(0.1234)


def test_digest_cost_falls_back_to_previous_digest_window(tmp_path) -> None:
    """Old spend rows without digest IDs are grouped by digest boundaries."""
    store = ContentStore(db_path=tmp_path / "test.db")
    first_id = store.save_digest(
        "# First",
        "<p>First</p>",
        json.dumps({"articles_count": 1}),
    )
    store.db.execute(
        "UPDATE digests SET created_at = ? WHERE id = ?",
        ["2026-05-17T07:00:00+00:00", first_id],
    )
    second_id = store.save_digest(
        "# Second",
        "<p>Second</p>",
        json.dumps({"articles_count": 1}),
    )
    store.db.execute(
        "UPDATE digests SET created_at = ? WHERE id = ?",
        ["2026-05-17T07:10:00+00:00", second_id],
    )
    store.db["spending"].insert_all(
        [
            {
                "amount_usd": 0.01,
                "model": "openrouter/test",
                "tokens": 10,
                "recorded_at": "2026-05-17T07:05:00+00:00",
            },
            {
                "amount_usd": 0.02,
                "model": "openrouter/test",
                "tokens": 20,
                "recorded_at": "2026-05-17T07:09:00+00:00",
            },
        ],
    )

    cost = _digest_cost_usd(
        store,
        second_id,
        "2026-05-17T07:10:00+00:00",
        {},
    )

    assert cost == pytest.approx(0.03)


def test_ratings_api_prefers_digest_items(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The /api/ratings endpoint returns digest items, not raw articles."""
    data_root = tmp_path / "appdata"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))

    store = ContentStore()
    store.save_article(
        {
            "url": "https://legacy.example/x",
            "title": "Legacy Noise Title",
            "content": "x",
            "source": "s",
            "category": "General",
            "content_hash": ContentStore.content_hash("x"),
            "published_at": "",
            "collected_at": "2099-01-01T00:00:00+00:00",
        },
    )
    payload = {
        "digest_items": [
            {
                "id": 0,
                "title": "Digest Item Alpha",
                "url": "https://digest.example/a",
                "category": "Tech",
                "kind": "article",
            },
        ],
    }
    store.save_digest("# Hello", "<p>Hello</p>", json.dumps(payload))
    client = TestClient(create_app())

    ratings = client.get("/api/ratings", headers=_AUTH)
    assert ratings.status_code == 200
    items = ratings.json()
    titles = [r["title"] for r in items]
    assert "Digest Item Alpha" in titles
    assert "Legacy Noise Title" not in titles


def test_digest_config_api_persists_age_cutoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The admin digest settings API exposes and saves the age filter cutoff."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    initial = client.get("/api/config/digest", headers=_AUTH)
    assert initial.status_code == 200
    assert initial.json()["max_article_age_hours"] == 36

    saved = client.put(
        "/api/config/digest",
        headers=_AUTH,
        json={"max_article_age_hours": 72},
    )
    assert saved.status_code == 200

    updated = client.get("/api/config/digest", headers=_AUTH)
    assert updated.status_code == 200
    assert updated.json()["max_article_age_hours"] == 72

    invalid = client.put(
        "/api/config/digest",
        headers=_AUTH,
        json={"max_article_age_hours": -1},
    )
    assert invalid.status_code == 422
