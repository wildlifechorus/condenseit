"""Tests for PreferenceEngine: category/source scoring, time decay, stop-words,
profile_summary, score breakdown, bigrams, implicit signals, dismiss, and edge
cases."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from condenseit.learning.preference_engine import (
    _STOP_WORDS,
    PreferenceEngine,
    _bigrams,
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


# ---------------------------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------------------------


def test_rank_articles_returns_score_breakdown(store: ContentStore) -> None:
    """Every ranked article must include a non-None score_breakdown dict."""
    for i in range(5):
        url = f"https://a.test/{i}"
        _save_article(
            store, url, f"CVE story {i}", "cve exploit kernel", "Infosec", "Feed"
        )
        _rate(store, url, 5)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.35)
    art = {
        "url": "https://new.test/",
        "title": "New CVE exploit",
        "content": "cve exploit kernel",
        "category": "Infosec",
        "source": "Feed",
    }
    ranked = eng.rank_articles([art])
    assert "score_breakdown" in ranked[0]
    bd = ranked[0]["score_breakdown"]
    assert isinstance(bd, dict)
    # Core classical keys must always be present.
    expected_core_keys = {
        "keyword_high",
        "keyword_medium",
        "term_overlap",
        "bigram_overlap",
        "tfidf_cosine",
        "category",
        "source",
        "implicit_content",
        "implicit_category",
        "implicit_source",
        "synonym_boost",
    }
    # New AI-signal keys are also always present (default 0.0 when disabled).
    expected_ai_keys = {"embedding_similarity", "topic_score", "llm_rerank"}
    assert expected_core_keys.issubset(set(bd.keys()))
    assert expected_ai_keys.issubset(set(bd.keys()))


def test_score_breakdown_keyword_high_contributes(store: ContentStore) -> None:
    """High-priority keyword match should appear in the breakdown."""
    eng = _engine(store, min_ratings=1)
    art = {
        "url": "https://k.test/",
        "title": "Kubernetes vulnerability",
        "content": "kubernetes cluster",
        "category": "Tech",
        "source": "Feed",
    }
    ranked = eng.rank_articles([art], keyword_high={"kubernetes"})
    assert ranked[0]["score_breakdown"]["keyword_high"] == pytest.approx(2.0)


def test_score_breakdown_sums_to_preference_score(store: ContentStore) -> None:
    """The sum of all breakdown values must equal preference_score."""
    for i in range(5):
        url = f"https://b.test/{i}"
        _save_article(
            store, url, f"Python tips {i}", "python async coroutine", "Dev", "Feed"
        )
        _rate(store, url, 5)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.35)
    art = {
        "url": "https://c.test/",
        "title": "Async Python patterns",
        "content": "python async coroutine",
        "category": "Dev",
        "source": "Feed",
    }
    ranked = eng.rank_articles([art])
    bd = ranked[0]["score_breakdown"]
    numeric_total = round(sum(v for v in bd.values() if isinstance(v, (int, float))), 3)
    assert numeric_total == pytest.approx(ranked[0]["preference_score"], abs=0.01)


# ---------------------------------------------------------------------------
# Bigrams
# ---------------------------------------------------------------------------


def test_bigrams_extracted_from_title() -> None:
    """Bigrams should be consecutive stop-word-filtered word pairs."""
    result = _bigrams("supply chain attack vulnerability")
    assert "supply chain" in result
    assert "chain attack" in result


def test_bigrams_skips_stop_words() -> None:
    """Stop words must not appear in bigrams."""
    result = _bigrams("the kubernetes vulnerability")
    # 'the' is a stop word; 'kubernetes' and 'vulnerability' are both kept
    assert all("the" not in bg.split() for bg in result)


def test_bigrams_empty_string() -> None:
    assert _bigrams("") == []


def test_bigrams_single_word() -> None:
    assert _bigrams("kubernetes") == []


def test_liked_bigrams_boost_score(store: ContentStore) -> None:
    """Articles with bigrams matching liked-article titles rank higher."""
    for i in range(5):
        url = f"https://sc.test/{i}"
        _save_article(
            store,
            url,
            "supply chain vulnerability",
            "attack supply chain",
            "Infosec",
            "Feed",
        )
        _rate(store, url, 5)

    eng = _engine(store, min_ratings=5, tfidf_weight=0.0, category_weight=0.0)
    eng.learn_from_ratings()
    assert len(eng._liked_bigrams) > 0, "Expected bigrams in liked_bigrams"

    high = {
        "url": "https://n.test/1",
        "title": "supply chain compromise found",
        "content": "supply chain attack",
        "category": "Other",
        "source": "OtherFeed",
    }
    low = {
        "url": "https://n.test/2",
        "title": "Recipe for pasta",
        "content": "pasta tomato recipe",
        "category": "Other",
        "source": "OtherFeed",
    }
    ranked = eng.rank_articles([low, high])
    assert ranked[0]["url"] == high["url"]


# ---------------------------------------------------------------------------
# 3-char token support
# ---------------------------------------------------------------------------


def test_cve_three_char_token_included() -> None:
    """'CVE' (3 chars) must now appear in tokenized output."""
    tokens = _tokenize("CVE-2024-1234 critical vulnerability")
    assert "cve" in tokens


def test_api_three_char_token_included() -> None:
    """'API' (3 chars) must now appear in tokenized output."""
    tokens = _tokenize("API authentication bypass")
    assert "api" in tokens


def test_llm_three_char_token_included() -> None:
    """'LLM' (3 chars) must now appear in tokenized output."""
    tokens = _tokenize("LLM jailbreak technique")
    assert "llm" in tokens


# ---------------------------------------------------------------------------
# Implicit signals
# ---------------------------------------------------------------------------


def _dismiss(store: ContentStore, url: str, days_ago: int = 0) -> None:
    """Record a dismiss for a URL, optionally back-dating it."""
    dismissed_at = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    store.db["dismissed_articles"].upsert(
        {"url": url, "title": "", "dismissed_at": dismissed_at},
        pk="url",
    )


def _save_read(store: ContentStore, url: str, days_ago: int = 0) -> None:
    """Mark URL as read, optionally back-dating it."""
    read_at = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    store.db["read_articles"].upsert(
        {"url": url, "read_at": read_at, "title": ""},
        pk="url",
    )


def test_dismissed_articles_table_created(store: ContentStore) -> None:
    """dismissed_articles table must exist after store initialisation."""
    assert "dismissed_articles" in store.db.table_names()


def test_dismiss_article_store_method(store: ContentStore) -> None:
    """dismiss_article() must record the URL and also mark as read."""
    _save_article(store, "https://d.test/1", "Article", "content", "Tech", "Feed")
    store.dismiss_article("https://d.test/1", title="Article")
    assert "https://d.test/1" in store.get_dismissed_urls()
    assert "https://d.test/1" in store.get_read_urls()


def test_dismissed_count(store: ContentStore) -> None:
    for i in range(3):
        url = f"https://dis.test/{i}"
        _save_article(store, url, f"Art {i}", "content", "Tech", "Feed")
        store.dismiss_article(url)
    assert store.dismissed_count() == 3


def test_implicit_dismissed_lowers_score(store: ContentStore) -> None:
    """Dismissing articles from a category should lower its implicit score."""
    for i in range(5):
        url = f"https://dis-cat.test/{i}"
        _save_article(
            store,
            url,
            f"Recipe {i}",
            "cooking pasta kitchen recipe",
            "Lifestyle",
            "LifeFeed",
        )
        _rate(store, url, 3)  # neutral explicit rating

    # Dismiss several articles from Lifestyle.
    for i in range(3):
        _dismiss(store, f"https://dis-cat.test/{i}")

    eng = PreferenceEngine(
        store,
        min_ratings=1,
        tfidf_weight=0.0,
        category_weight=0.6,
        source_weight=0.0,
        implicit_signal_weight=0.8,
    )
    eng.learn_from_ratings()

    # The implicit category score for Lifestyle should be negative (< 0).
    imp_score = eng._implicit_category_scores.get("Lifestyle", 0.0)
    assert imp_score < 0, (
        f"Expected negative implicit score for dismissed category, got {imp_score}"
    )


def test_implicit_saved_boosts_score(store: ContentStore) -> None:
    """Saving articles for later should produce a positive implicit signal."""
    for i in range(5):
        url = f"https://rl.test/{i}"
        _save_article(
            store, url, f"Infosec {i}", "security exploit cve", "Infosec", "SecFeed"
        )
        _rate(store, url, 3)  # neutral explicit
        store.db["read_later"].upsert(
            {
                "url": url,
                "title": f"Infosec {i}",
                "summary": "security exploit cve",
                "tldr": "",
                "key_takeaways": "[]",
                "source": "SecFeed",
                "category": "Infosec",
                "kind": "article",
                "published_at": "",
                "saved_at": datetime.now(UTC).isoformat(),
            },
            pk="url",
        )

    eng = PreferenceEngine(
        store,
        min_ratings=1,
        tfidf_weight=0.0,
        category_weight=0.6,
        source_weight=0.0,
        implicit_signal_weight=0.8,
    )
    eng.learn_from_ratings()

    imp_score = eng._implicit_category_scores.get("Infosec", 0.0)
    assert imp_score > 0, (
        f"Expected positive implicit score for saved category, got {imp_score}"
    )


def test_implicit_disabled_when_weight_zero(store: ContentStore) -> None:
    """With implicit_signal_weight=0, implicit profiles must stay empty."""
    _save_article(store, "https://z.test/1", "Article", "content", "Tech", "Feed")
    _rate(store, "https://z.test/1", 5)
    _dismiss(store, "https://z.test/1")

    eng = PreferenceEngine(store, min_ratings=1, implicit_signal_weight=0.0)
    eng.learn_from_ratings()
    assert len(eng._implicit_category_scores) == 0
    assert len(eng._implicit_liked_terms) == 0
    assert len(eng._implicit_disliked_terms) == 0


# ---------------------------------------------------------------------------
# Topic synonyms
# ---------------------------------------------------------------------------


def test_synonym_boost_applies_when_synonym_present(store: ContentStore) -> None:
    """An article containing 'k8s' should benefit from profile weight for
    'kubernetes' when they are in the same synonym group."""
    for i in range(5):
        url = f"https://k8s.test/{i}"
        _save_article(
            store,
            url,
            f"Kubernetes deploy {i}",
            "kubernetes cluster deployment",
            "Dev",
            "Feed",
        )
        _rate(store, url, 5)

    synonyms = {"kube": ["kubernetes", "k8s", "kubectl", "helm"]}
    eng = PreferenceEngine(
        store,
        min_ratings=5,
        tfidf_weight=0.0,
        category_weight=0.0,
        source_weight=0.0,
        implicit_signal_weight=0.0,
        topic_synonyms=synonyms,
    )

    with_syn = {
        "url": "https://new.test/1",
        "title": "k8s performance tips",
        "content": "k8s cluster configuration",
        "category": "Other",
        "source": "OtherFeed",
    }
    without_syn = {
        "url": "https://new.test/2",
        "title": "pasta recipe today",
        "content": "pasta tomato kitchen",
        "category": "Other",
        "source": "OtherFeed",
    }

    ranked = eng.rank_articles([without_syn, with_syn])
    assert ranked[0]["url"] == with_syn["url"]
    assert ranked[0]["score_breakdown"]["synonym_boost"] > 0


# ---------------------------------------------------------------------------
# Profile summary new fields
# ---------------------------------------------------------------------------


def test_profile_summary_includes_new_fields(store: ContentStore) -> None:
    """profile_summary must include all new fields added in this overhaul."""
    eng = _engine(store, min_ratings=5)
    summary = eng.profile_summary()

    for field in (
        "rating_distribution",
        "implicit_read_count",
        "implicit_saved_count",
        "implicit_dismissed_count",
        "implicit_learning_active",
        "oldest_rating_decay",
        "decay_half_life_days",
        "top_liked_bigrams",
        "top_disliked_bigrams",
    ):
        assert field in summary, f"Missing field: {field}"


def test_profile_summary_rating_distribution_structure(
    store: ContentStore,
) -> None:
    """rating_distribution must have keys '1'-'5' with integer counts."""
    for i in range(5):
        url = f"https://rd.test/{i}"
        _save_article(store, url, f"A {i}", "content", "Tech", "Feed")
        _rate(store, url, 4)

    eng = _engine(store, min_ratings=5)
    dist = eng.profile_summary()["rating_distribution"]
    assert set(dist.keys()) == {"1", "2", "3", "4", "5"}
    assert dist["4"] == 5
    assert dist["1"] == 0


# ---------------------------------------------------------------------------
# API endpoints (dismiss, weights)
# ---------------------------------------------------------------------------


def test_api_dismiss_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """POST /api/dismiss must record the URL in dismissed_articles."""
    from fastapi.testclient import TestClient

    from condenseit.web.app import create_app

    data_root = tmp_path / "appdata"
    data_root.mkdir()
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_root))

    store_local = ContentStore(db_path=data_root / "condenseit.db")
    _save_article(
        store_local, "https://dis.test/a", "Some Article", "content", "Tech", "Feed"
    )

    _auth = {"Authorization": "Bearer condenseit"}
    client = TestClient(create_app())
    resp = client.post(
        "/api/dismiss",
        json={"url": "https://dis.test/a", "title": "Some Article"},
        headers=_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_api_ranking_weights_get(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GET /api/preferences/weights must return a dict with all weight keys."""
    from fastapi.testclient import TestClient

    from condenseit.web.app import create_app

    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "data"))
    _auth = {"Authorization": "Bearer condenseit"}
    client = TestClient(create_app())
    resp = client.get("/api/preferences/weights", headers=_auth)
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "tfidf_preference_weight",
        "category_preference_weight",
        "source_preference_weight",
        "implicit_signal_weight",
        "rating_decay_half_life_days",
        "min_ratings_for_learning",
    ):
        assert key in data


def test_api_ranking_weights_put(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """PUT /api/preferences/weights must persist values and be read back."""
    from fastapi.testclient import TestClient

    from condenseit.web.app import create_app

    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path / "wdata"))
    _auth = {"Authorization": "Bearer condenseit"}
    client = TestClient(create_app())

    resp = client.put(
        "/api/preferences/weights",
        json={"tfidf_preference_weight": 0.75, "rating_decay_half_life_days": 60},
        headers=_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp2 = client.get("/api/preferences/weights", headers=_auth)
    data = resp2.json()
    assert data["tfidf_preference_weight"] == pytest.approx(0.75)
    assert data["rating_decay_half_life_days"] == 60


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


# ---------------------------------------------------------------------------
# Negative keyword penalty + category gate evidence
# ---------------------------------------------------------------------------


def test_negative_keyword_single_word_penalty(store: ContentStore) -> None:
    """A single disliked word penalises only the matching article."""
    eng = _engine(store)
    arts = [
        {"url": "a", "title": "Bitcoin crypto rally surges", "content": ""},
        {"url": "b", "title": "New Rust language release", "content": ""},
    ]
    ranked = eng.rank_articles(arts, keyword_negative={"crypto"})
    by_url = {a["url"]: a for a in ranked}
    assert by_url["a"]["score_breakdown"]["keyword_negative"] == -2.0
    assert by_url["b"]["score_breakdown"]["keyword_negative"] == 0.0
    # The penalised article sinks below the neutral one.
    assert [a["url"] for a in ranked] == ["b", "a"]


def test_negative_keyword_multiword_requires_all_words(store: ContentStore) -> None:
    """A multi-word disliked phrase only matches when every word is present."""
    eng = _engine(store)
    arts = [
        {"url": "a", "title": "Celebrity gossip news today", "content": ""},
        {"url": "b", "title": "Celebrity chef opens restaurant", "content": ""},
    ]
    ranked = eng.rank_articles(arts, keyword_negative={"celebrity news"})
    by_url = {a["url"]: a for a in ranked}
    assert by_url["a"]["score_breakdown"]["keyword_negative"] == -2.0
    assert by_url["b"]["score_breakdown"]["keyword_negative"] == 0.0


def test_category_rating_counts_and_combined_scores(store: ContentStore) -> None:
    """Counts track evidence per category; combined scores reflect sentiment."""
    for i in range(4):
        _save_article(store, f"n{i}", f"news story {i}", "body", "News", "src")
        _rate(store, f"n{i}", 1)
    for i in range(2):
        _save_article(store, f"t{i}", f"tech story {i}", "body", "Tech", "src")
        _rate(store, f"t{i}", 5)

    eng = _engine(store)
    eng.learn_from_ratings()

    assert eng.category_rating_counts() == {"News": 4, "Tech": 2}
    scores = eng.combined_category_scores()
    assert scores["News"] < 0 < scores["Tech"]
