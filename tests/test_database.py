from pathlib import Path

from click.testing import CliRunner

from condenseit.cli import cli
from condenseit.store.database import ContentStore


def test_migrate_applies_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    path = ContentStore.migrate(db_path=db_path)
    assert path == db_path
    assert db_path.is_file()
    store = ContentStore(db_path=db_path)
    assert "articles" in store.db.table_names()
    store.close()


def test_migrate_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["migrate"])
    assert result.exit_code == 0, result.output
    assert "Migrations applied" in result.output
    assert (tmp_path / "condenseit.db").is_file()


def test_deduplicate_new_article(tmp_path: Path) -> None:
    store = ContentStore(db_path=tmp_path / "test.db")
    article = {
        "url": "https://example.com/a",
        "title": "Test",
        "content": "Hello world",
        "source": "Example",
        "category": "General",
        "content_hash": ContentStore.content_hash("Hello world"),
        "published_at": "2026-01-01T00:00:00+00:00",
        "collected_at": "2026-01-01T00:00:00+00:00",
    }
    fresh = store.deduplicate([article])
    assert len(fresh) == 1
    expected_hash = article["content_hash"]

    same_hash_again = {
        **article,
        "collected_at": "2026-06-01T12:00:00+00:00",
        "title": "Test renamed",
    }
    fresh_again = store.deduplicate([same_hash_again])
    assert len(fresh_again) == 0
    row = store.db["articles"].get(article["url"])
    assert row["collected_at"] == "2026-06-01T12:00:00+00:00"
    assert row["title"] == "Test renamed"
    assert row["content_hash"] == expected_hash
