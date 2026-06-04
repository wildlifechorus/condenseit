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


def test_gate_excludes_strongly_disliked_category() -> None:
    """A category at or below the exclude threshold gets no slots at all."""
    ranked = [
        _art("g1", "General News", 5.0),
        _art("g2", "General News", 4.0),
        _art("u1", "Ukraine", 1.0),
        _art("a1", "AI News", 0.5),
    ]
    out = select_balanced_digest_articles(
        ranked,
        max_n=10,
        category_scores={"General News": -1.8, "Ukraine": 0.7, "AI News": 0.4},
    )
    cats = [a["category"] for a in out]
    assert "General News" not in cats
    assert set(cats) == {"Ukraine", "AI News"}


def test_gate_demotes_mildly_disliked_category() -> None:
    """A demoted category keeps at most ``demote_cap`` articles and no
    guaranteed slot."""
    ranked = [
        _art("t1", "General Tech", 5.0),
        _art("t2", "General Tech", 4.0),
        _art("t3", "General Tech", 3.0),
        _art("u1", "Ukraine", 2.0),
    ]
    out = select_balanced_digest_articles(
        ranked,
        max_n=10,
        category_scores={"General Tech": -0.7, "Ukraine": 0.5},
        demote_cap=1,
    )
    tech = [a for a in out if a["category"] == "General Tech"]
    assert len(tech) == 1
    assert tech[0]["url"] == "t1"  # highest-ranked survivor


def test_gate_unknown_category_is_normal() -> None:
    """Categories absent from ``category_scores`` keep classic behaviour."""
    ranked = [
        _art("f1", "FPV News", 5.0),
        _art("f2", "FPV News", 4.0),
        _art("g1", "General News", 1.0),
    ]
    out = select_balanced_digest_articles(
        ranked,
        max_n=10,
        category_scores={"General News": -1.8},  # FPV not gated
    )
    cats = [a["category"] for a in out]
    assert "FPV News" in cats
    assert "General News" not in cats


def test_gate_safety_net_never_empties_digest() -> None:
    """If every category is excluded, fall back to the top global articles."""
    ranked = [_art("a", "A", 3.0), _art("b", "B", 2.0)]
    out = select_balanced_digest_articles(
        ranked,
        max_n=5,
        category_scores={"A": -3.0, "B": -3.0},
    )
    assert [a["url"] for a in out] == ["a", "b"]
