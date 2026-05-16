"""Ratings JSON import helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from condenseit.config import AppConfig
from condenseit.ratings_import import (
    apply_configured_ratings_import,
    import_ratings_json_text,
    import_ratings_url,
    parse_ratings_payload,
)
from condenseit.store.database import ContentStore


def test_parse_ratings_payload_dict() -> None:
    data = {
        "ratings": [
            {"url": "https://a.example/x", "rating": 5},
            {"url": "", "rating": 3},
            {"url": "https://b.example/y", "rating": 0},
            {"url": "https://c.example/z", "rating": 2},
        ],
    }
    pairs = parse_ratings_payload(data)
    assert pairs == [
        ("https://a.example/x", 5),
        ("https://c.example/z", 2),
    ]


def test_parse_ratings_payload_list() -> None:
    data = [{"url": "https://x.test/", "rating": 4}]
    assert parse_ratings_payload(data) == [("https://x.test/", 4)]


def test_import_ratings_json_text(tmp_path: Path) -> None:
    db = tmp_path / "d.db"
    store = ContentStore(db_path=db)
    body = json.dumps(
        {"version": 1, "ratings": [{"url": "https://u.test/a", "rating": 1}]},
    )
    n = import_ratings_json_text(store, body)
    assert n == 1
    rows = list(store.db.query("SELECT url, rating FROM ratings"))
    assert len(rows) == 1
    assert rows[0]["url"] == "https://u.test/a"
    assert rows[0]["rating"] == 1


def test_apply_configured_ratings_import_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "d.db"
    store = ContentStore(db_path=db)
    jf = tmp_path / "r.json"
    jf.write_text(
        json.dumps({"ratings": [{"url": "https://p.test/1", "rating": 5}]}),
        encoding="utf-8",
    )
    monkeypatch.delenv("CONDENSEIT_RATINGS_IMPORT_PATH", raising=False)
    monkeypatch.delenv("CONDENSEIT_RATINGS_IMPORT_URL", raising=False)
    cfg = AppConfig()
    cfg.digest_pwa.ratings_import_path = str(jf)
    n = apply_configured_ratings_import(store, cfg)
    assert n == 1


def test_import_ratings_url_mocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = tmp_path / "d.db"
    store = ContentStore(db_path=db)

    class FakeResp:
        status_code = 200
        text = json.dumps(
            {"ratings": [{"url": "https://h.test/z", "rating": 3}]},
        )

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResp:
            assert "https://remote" in url
            return FakeResp()

    monkeypatch.setattr("condenseit.ratings_import.httpx.Client", FakeClient)
    n = import_ratings_url(store, "https://remote.example/r.json")
    assert n == 1
