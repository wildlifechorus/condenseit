"""Tests for PreferenceEngine: category/source scoring, time decay, stop-words,
profile_summary, and edge cases."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from condenseit.learning.preference_engine import (
    _STOP_WORDS,
    PreferenceEngine,
    _time_decay,
    _tokenize,
)
from condenseit.store.database import ContentStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> ContentStore:
    """Fresh in-memory SQLite store backed by a temp file."""
    return ContentStore(db_path=tmp_path / "test.db")


def _save_article(
    store: ContentStore,
    url: str,
    title: str,
    content: str,
    category: str,
    source: str,
) -> None:
    store.save_article(
        {
            "url": url,
            "title": title,
            "content": content,
            "source": source,
            "category": category,
            "content_hash": ContentStore.content_hash(content),
            "published_at": "",
            "collected_at": datetime.now(UTC).isoformat(),
        },
    )


def _rate(
    store: ContentStore,
    url: str,
    rating: int,
    days_ago: int = 0,
) -> None:
    """Rate a URL, optionally back-dating ``rated_at``."""
    rated_at = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    store.db["ratings"].upsert(
        {"url": url, "rating": rating, "rated_at": rated_at},
        pk="url",
    )


def _engine(
    store: ContentStore,
    min_ratings: int = 1,
    decay_half_life_days: int = 30,
    category_weight: float = 0.6,
    source_weight: float = 0.3,
    tfidf_weight: float = 0.0,
) -> PreferenceEngine:
    return PreferenceEngine(
        store,
        min_ratings=min_ratings,
        tfidf_weight=tfidf_weight,
        category_weight=category_weight,
        source_weight=source_weight,
        decay_half_life_days=decay_half_life_days,
    )


# ---------------------------------------------------------------------------
# Stop-word tests
# ---------------------------------------------------------------------------


def test_stop_words_excluded_from_tokenize() -> None:
    """Known stop-words must not appear in token output."""
    stop_samples = ["article", "update", "release", "using", "https", "news"]
    result = _tokenize(" ".join(stop_samples))
    for word in stop_samples:
        assert word not in result, f"'{word}' should be a stop-word"


def test_tokenize_preserves_meaningful_terms() -> None:
    tokens = _tokenize("kubernetes exploit vulnerability fpvdrone")
    assert "kubernetes" in tokens
    assert "exploit" in tokens
    assert "vulnerability" in tokens
    assert "fpvdrone" in tokens


def test_stop_words_is_frozenset() -> None:
    assert isinstance(_STOP_WORDS, frozenset)


def test_short_tokens_excluded() -> None:
    """Words shorter than 4 characters are filtered out by the regex."""
    tokens = _tokenize("a is at the go py")
    assert tokens == []


# ---------------------------------------------------------------------------
# Time-decay helper
# ---------------------------------------------------------------------------


def test_time_decay_today_is_one() -> None:
    now = datetime.now(UTC)
    rated_at = now.isoformat()
    lam = 0.0231  # half-life 30 days
    result = _time_decay(rated_at, now, lam)
    assert abs(result - 1.0) < 0.01


def test_time_decay_half_life() -> None:
    now = datetime.now(UTC)
    rated_at = (now - timedelta(days=30)).isoformat()
    lam = 0.02310  # ln(2)/30
    result = _time_decay(rated_at, now, lam)
    assert abs(result - 0.5) < 0.02


def test_time_decay_old_rating_much_lower() -> None:
    now = datetime.now(UTC)
    lam = 0.02310
    recent = _time_decay((now - timedelta(days=5)).isoformat(), now, lam)
    old = _time_decay((now - timedelta(days=90)).isoformat(), now, lam)
    assert recent > old


def test_time_decay_invalid_date_returns_one() -> None:
    now = datetime.now(UTC)
    assert _time_decay("not-a-date", now, 0.02310) == 1.0
    assert _time_decay("", now, 0.02310) == 1.0


# ---------------------------------------------------------------------------
# Engine — minimum ratings gate
# ---------------------------------------------------------------------------


def test_engine_no_learning_below_threshold(store: ContentStore) -> None:
    """With fewer ratings than min_ratings, scores stay at 0.0."""
    _save_article(
        store, "https://a.test/", "Kubernetes CVE", "cve kubernetes", "Infosec", "Feed"
    )
    _rate(store, "https://a.test/", 5)

    eng = _engine(store, min_ratings=5)
    articles = [
        {
            "url": "https://a.test/",
            "title": "Kubernetes CVE",
            "content": "cve kubernetes",
            "category": "Infosec",
            "source": "Feed",
        }
    ]
    ranked = eng.rank_articles(articles)
    assert ranked[0]["preference_score"] == 0.0


def test_engine_learns_after_threshold(store: ContentStore) -> None:
    """Once min_ratings is reached, liked articles rank higher."""
    for i in range(5):
        url = f"https://infosec.test/{i}"
        _save_article(
            store, url, "CVE Report", "cve exploit vulnerability", "Infosec", "Feed"
        )
        _rate(store, url, 5)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.35)
    high = {
        "url": "https://new.test/1",
        "title": "New CVE exploit",
        "content": "cve exploit vulnerability",
        "category": "Infosec",
        "source": "Feed",
    }
    low = {
        "url": "https://new.test/2",
        "title": "Recipe book",
        "content": "baking bread flour",
        "category": "Lifestyle",
        "source": "Other",
    }
    ranked = eng.rank_articles([low, high])
    assert ranked[0]["url"] == high["url"]


# ---------------------------------------------------------------------------
# Category preference scoring
# ---------------------------------------------------------------------------


def test_category_preference_boosts_liked_category(store: ContentStore) -> None:
    """Articles in a consistently-high-rated category rank above others."""
    # 5 liked "Infosec" articles.
    for i in range(5):
        url = f"https://infosec.test/{i}"
        _save_article(
            store,
            url,
            f"Infosec story {i}",
            "security cve firewall",
            "Infosec",
            "SecFeed",
        )
        _rate(store, url, 5)

    # 5 disliked "Lifestyle" articles.
    for i in range(5):
        url = f"https://life.test/{i}"
        _save_article(
            store,
            url,
            f"Recipe {i}",
            "cooking recipes kitchen",
            "Lifestyle",
            "LifeFeed",
        )
        _rate(store, url, 1)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.0)
    infosec = {
        "url": "https://new.test/a",
        "title": "Firewall bypass",
        "content": "firewall bypass technique",
        "category": "Infosec",
        "source": "SecFeed",
    }
    lifestyle = {
        "url": "https://new.test/b",
        "title": "Pasta recipe",
        "content": "pasta tomato basil",
        "category": "Lifestyle",
        "source": "LifeFeed",
    }
    ranked = eng.rank_articles([lifestyle, infosec])
    assert ranked[0]["url"] == infosec["url"], "Infosec should rank first"


def test_category_score_neutral_for_three_star(store: ContentStore) -> None:
    """Articles with all-3-star category ratings contribute 0 category score."""
    for i in range(5):
        url = f"https://neutral.test/{i}"
        _save_article(
            store, url, f"Neutral {i}", "neutral content here", "General", "Feed"
        )
        _rate(store, url, 3)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.0)
    eng.learn_from_ratings()
    # mean = 3.0, score = 3.0 - 3.0 = 0.0
    assert eng._category_scores.get("General", 0.0) == pytest.approx(0.0, abs=0.05)


def test_category_weight_zero_disables_category_scoring(store: ContentStore) -> None:
    """category_weight=0 means the category signal does not add to the score.

    We verify this by comparing two engines against the same article:
    one with positive category_weight and one with zero. The engine with
    category_weight=0 must produce a score <= the one with the weight active.
    """
    for i in range(5):
        url = f"https://loved.test/{i}"
        _save_article(
            store, url, f"Infosec {i}", "peculiarsecurityword", "Infosec", "Feed"
        )
        _rate(store, url, 5)

    art = {
        "url": "https://new.test/",
        "title": "Peculiarsecurityword headline",
        "content": "peculiarsecurityword",
        "category": "Infosec",
        "source": "Feed",
    }

    eng_with = _engine(store, min_ratings=5, tfidf_weight=0.0, category_weight=0.6)
    eng_without = _engine(store, min_ratings=5, tfidf_weight=0.0, category_weight=0.0)

    score_with = eng_with.rank_articles([art])[0]["preference_score"]
    score_without = eng_without.rank_articles([art])[0]["preference_score"]

    # Category contributes +ve score (liked category), so weight=0.6 must yield higher.
    assert score_with > score_without


# ---------------------------------------------------------------------------
# Source preference scoring
# ---------------------------------------------------------------------------


def test_source_preference_boosts_liked_source(store: ContentStore) -> None:
    """Articles from a consistently high-rated source rank above others."""
    for i in range(5):
        url = f"https://good-feed.test/{i}"
        _save_article(
            store,
            url,
            f"Good article {i}",
            "interesting topic content",
            "Tech",
            "GoodFeed",
        )
        _rate(store, url, 5)

    for i in range(5):
        url = f"https://bad-feed.test/{i}"
        _save_article(
            store, url, f"Bad article {i}", "boring topic content", "Tech", "BadFeed"
        )
        _rate(store, url, 1)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.0, category_weight=0.0)
    good = {
        "url": "https://new.test/g",
        "title": "GoodFeed new",
        "content": "interesting new",
        "category": "Tech",
        "source": "GoodFeed",
    }
    bad = {
        "url": "https://new.test/b",
        "title": "BadFeed new",
        "content": "boring new",
        "category": "Tech",
        "source": "BadFeed",
    }
    ranked = eng.rank_articles([bad, good])
    assert ranked[0]["url"] == good["url"], "GoodFeed article should rank first"


def test_source_scores_in_learned_state(store: ContentStore) -> None:
    """After learning, source scores have expected sign."""
    for i in range(5):
        url = f"https://liked.test/{i}"
        _save_article(store, url, f"Liked {i}", "liked content", "Tech", "LikedSource")
        _rate(store, url, 5)
    for i in range(5):
        url = f"https://disliked.test/{i}"
        _save_article(
            store, url, f"Disliked {i}", "disliked content", "Tech", "DislikedSource"
        )
        _rate(store, url, 1)

    eng = _engine(store, min_ratings=5)
    eng.learn_from_ratings()
    assert eng._source_scores.get("LikedSource", 0.0) > 0
    assert eng._source_scores.get("DislikedSource", 0.0) < 0


# ---------------------------------------------------------------------------
# Time decay integration
# ---------------------------------------------------------------------------


def test_old_ratings_have_less_effect_than_recent(store: ContentStore) -> None:
    """A recent negative rating should outweigh an old positive one."""
    # Old liked article (90 days ago).
    _save_article(
        store,
        "https://old.test/like",
        "Old liked",
        "security audit cve exploit",
        "Infosec",
        "OldFeed",
    )
    _rate(store, "https://old.test/like", 5, days_ago=90)

    # Recent disliked article with same terms (1 day ago).
    _save_article(
        store,
        "https://new.test/dislike",
        "New disliked",
        "security audit cve exploit",
        "Infosec",
        "OldFeed",
    )
    _rate(store, "https://new.test/dislike", 1, days_ago=1)

    eng = _engine(
        store,
        min_ratings=1,
        decay_half_life_days=30,
        tfidf_weight=0.0,
        category_weight=0.0,
    )
    eng.learn_from_ratings()

    # Recent dislikes should outweigh stale likes for the same terms.
    liked_total = sum(eng._liked_terms.values())
    disliked_total = sum(eng._disliked_terms.values())
    assert disliked_total > liked_total, (
        f"Recent dislike ({disliked_total:.2f}) should outweigh "
        f"old like ({liked_total:.2f})"
    )


def test_very_large_half_life_approximates_no_decay(store: ContentStore) -> None:
    """A huge half-life should give essentially equal weight to old/new ratings."""
    _save_article(store, "https://a.test/", "Article", "security", "Tech", "Feed")
    _rate(store, "https://a.test/", 5, days_ago=365)

    eng_decay = _engine(store, min_ratings=1, decay_half_life_days=30, tfidf_weight=0.0)
    eng_nodecay = _engine(
        store, min_ratings=1, decay_half_life_days=36500, tfidf_weight=0.0
    )
    eng_decay.learn_from_ratings()
    eng_nodecay.learn_from_ratings()

    # With huge half-life, liked term weight should be near 1.0 not 0.0006.
    nodecay_weight = sum(eng_nodecay._liked_terms.values())
    decay_weight = sum(eng_decay._liked_terms.values())
    assert nodecay_weight > decay_weight * 10


# ---------------------------------------------------------------------------
# profile_summary
# ---------------------------------------------------------------------------


def test_profile_summary_shape_no_ratings(store: ContentStore) -> None:
    eng = _engine(store, min_ratings=5)
    summary = eng.profile_summary()
    assert summary["rating_count"] == 0
    assert summary["learning_active"] is False
    assert isinstance(summary["top_liked_terms"], list)
    assert isinstance(summary["category_preferences"], list)
    assert isinstance(summary["source_preferences"], list)


def test_profile_summary_with_ratings(store: ContentStore) -> None:
    for i in range(5):
        url = f"https://infosec.test/{i}"
        _save_article(
            store,
            url,
            f"CVE {i}",
            "cve exploit kernel vulnerability",
            "Infosec",
            "SecFeed",
        )
        _rate(store, url, 5)

    eng = _engine(store, min_ratings=5)
    summary = eng.profile_summary()
    assert summary["learning_active"] is True
    assert summary["rating_count"] == 5
    assert len(summary["top_liked_terms"]) > 0
    assert summary["category_preferences"][0]["category"] == "Infosec"
    assert summary["category_preferences"][0]["score"] > 0


def test_profile_summary_category_scores_sorted_desc(store: ContentStore) -> None:
    """Category preferences must be sorted from highest to lowest score."""
    for i in range(3):
        url_liked = f"https://a.test/{i}"
        _save_article(store, url_liked, f"A {i}", "content alpha", "Liked", "Feed")
        _rate(store, url_liked, 5)
        url_disliked = f"https://b.test/{i}"
        _save_article(store, url_disliked, f"B {i}", "content beta", "Disliked", "Feed")
        _rate(store, url_disliked, 1)

    eng = _engine(store, min_ratings=1)
    summary = eng.profile_summary()
    scores = [c["score"] for c in summary["category_preferences"]]
    assert scores == sorted(scores, reverse=True)


def test_profile_summary_earliest_latest_dates(store: ContentStore) -> None:
    for i in range(3):
        url = f"https://dated.test/{i}"
        _save_article(store, url, f"Art {i}", "content", "Tech", "Feed")
        _rate(store, url, 4, days_ago=i * 10)

    eng = _engine(store, min_ratings=1)
    summary = eng.profile_summary()
    assert summary["earliest_rating"] != ""
    assert summary["latest_rating"] != ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_engine_empty_articles_list(store: ContentStore) -> None:
    eng = _engine(store, min_ratings=1)
    ranked = eng.rank_articles([])
    assert ranked == []


def test_engine_article_without_url_still_ranked(store: ContentStore) -> None:
    art = {
        "title": "No URL",
        "content": "content",
        "category": "Tech",
        "source": "Feed",
    }
    eng = _engine(store, min_ratings=1)
    ranked = eng.rank_articles([art])
    assert len(ranked) == 1


def test_engine_articles_without_content(store: ContentStore) -> None:
    arts = [
        {
            "url": f"https://x.test/{i}",
            "title": "",
            "content": "",
            "category": "Tech",
            "source": "Feed",
        }
        for i in range(3)
    ]
    eng = _engine(store, min_ratings=1)
    ranked = eng.rank_articles(arts)
    assert len(ranked) == 3


def test_api_preferences_profile_endpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The /api/preferences/profile endpoint returns a valid JSON object."""
    from fastapi.testclient import TestClient

    from condenseit.web.app import create_app

    _auth = {"Authorization": "Bearer condenseit"}
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())
    resp = client.get("/api/preferences/profile", headers=_auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "rating_count" in data
    assert "learning_active" in data
    assert isinstance(data["top_liked_terms"], list)


def test_digest_detail_includes_ratings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The /api/digests/latest response includes rating field on each item."""
    from fastapi.testclient import TestClient

    from condenseit.web.app import create_app

    data_root = tmp_path / "appdata"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))

    store = ContentStore(db_path=data_root / "condenseit.db")
    payload = {
        "digest_items": [
            {
                "url": "https://r.test/a",
                "title": "Rated",
                "kind": "article",
                "summary": "S",
                "source": "",
                "category": "Tech",
            },
        ],
    }
    store.save_digest("# D", "<p>D</p>", json.dumps(payload))
    store.rate_article("https://r.test/a", 4)

    _auth = {"Authorization": "Bearer condenseit"}
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))
    client = TestClient(create_app())
    resp = client.get("/api/digests/latest", headers=_auth)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["rating"] == 4
