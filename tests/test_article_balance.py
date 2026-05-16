"""Tests for category-balanced digest article selection."""

from __future__ import annotations

from condenseit.pipeline.article_balance import select_balanced_digest_articles


def _art(url: str, category: str, score: float) -> dict[str, object]:
    return {
        "url": url,
        "title": url,
        "category": category,
        "preference_score": score,
    }


def test_balanced_selection_includes_each_category_when_room() -> None:
    """Skewed global rank should still surface every category once."""
    ranked = [
        _art("i1", "Infosec News", 9.0),
        _art("i2", "Infosec News", 8.0),
        _art("i3", "Infosec News", 7.0),
        _art("g1", "General News", 2.0),
        _art("f1", "FPV News", 1.0),
    ]
    out = select_balanced_digest_articles(ranked, max_n=5)
    urls = [str(a["url"]) for a in out]
    assert urls[:3] == ["i1", "g1", "f1"]
    assert urls[3:] == ["i2", "i3"]


def test_respects_max_n_less_than_category_count() -> None:
    ranked = [
        _art("a", "A", 3.0),
        _art("b", "B", 2.0),
        _art("c", "C", 1.0),
    ]
    out = select_balanced_digest_articles(ranked, max_n=2)
    assert [a["url"] for a in out] == ["a", "b"]


def test_single_category_behaves_like_ordered_truncate() -> None:
    ranked = [_art("x1", "News", 3.0), _art("x2", "News", 2.0), _art("x3", "News", 1.0)]
    out = select_balanced_digest_articles(ranked, max_n=2)
    assert [a["url"] for a in out] == ["x1", "x2"]


def test_skips_blank_urls_and_deduplicates() -> None:
    ranked = [
        _art("", "A", 5.0),
        _art("u1", "A", 4.0),
        _art("u1", "A", 3.0),
    ]
    out = select_balanced_digest_articles(ranked, max_n=5)
    assert [a["url"] for a in out] == ["u1"]


def test_empty_ranked() -> None:
    assert select_balanced_digest_articles([], max_n=5) == []
