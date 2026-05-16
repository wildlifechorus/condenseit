"""Rating-based article ranking with category/source preferences and time decay.

Scoring tiers (all additive):
  1. Keyword boost   - configured high/medium keywords from config.yaml
  2. Term overlap    - liked/disliked terms from past rated articles (TF-IDF cosine)
  3. Category score  - mean rating per category minus 3.0 (neutral midpoint)
  4. Source score    - mean rating per feed/source minus 3.0

All rating rows are weighted by exponential time decay so recent tastes
matter more than stale ones. Decay factor: exp(-ln(2)/half_life * days).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from condenseit.store.database import ContentStore

# ---------------------------------------------------------------------------
# Stop-words: common English + tech-digest filler that dilutes term profiles.
# ---------------------------------------------------------------------------
_STOP_WORDS: frozenset[str] = frozenset(
    {
        # Short / generic connectives
        "that",
        "this",
        "with",
        "from",
        "have",
        "will",
        "your",
        "about",
        "into",
        "than",
        "been",
        "also",
        "more",
        "just",
        "some",
        "like",
        "over",
        "when",
        "only",
        "most",
        "very",
        "after",
        "other",
        "which",
        "these",
        "those",
        "their",
        "would",
        "could",
        "should",
        "first",
        "there",
        "then",
        "each",
        "such",
        "both",
        "even",
        "back",
        "well",
        "what",
        "where",
        "here",
        "make",
        "made",
        "come",
        "know",
        "take",
        "time",
        "year",
        "week",
        "month",
        "many",
        "last",
        "next",
        # Tech-digest filler
        "article",
        "update",
        "release",
        "using",
        "https",
        "http",
        "news",
        "read",
        "version",
        "post",
        "blog",
        "link",
        "share",
        "learn",
        "find",
        "help",
        "need",
        "want",
        "look",
        "said",
        "says",
        "note",
        "docs",
        "page",
        "site",
        "team",
        "repo",
        "code",
        "data",
        "user",
        "tool",
        "type",
        "list",
        "example",
        "based",
        "added",
        "fixed",
        "changed",
        "support",
        "works",
        "working",
        "check",
        "getting",
        "please",
        "allows",
        "without",
        "between",
        "through",
        "including",
        "following",
        "available",
        "provides",
        "requires",
        "improved",
    },
)


class PreferenceEngine:
    """Learns from star ratings and ranks incoming articles accordingly."""

    def __init__(
        self,
        store: ContentStore,
        min_ratings: int = 5,
        tfidf_weight: float = 0.35,
        category_weight: float = 0.6,
        source_weight: float = 0.3,
        decay_half_life_days: int = 30,
    ) -> None:
        self.store = store
        self.min_ratings = min_ratings
        self.tfidf_weight = tfidf_weight
        self.category_weight = category_weight
        self.source_weight = source_weight
        self.decay_half_life_days = max(1, decay_half_life_days)

        # Term-level profile built from liked/disliked articles.
        self._liked_terms: Counter[str] = Counter()
        self._disliked_terms: Counter[str] = Counter()
        self._profile_vec: Counter[str] = Counter()

        # Category and source preference scores (mean_rating - 3.0).
        self._category_scores: dict[str, float] = {}
        self._source_scores: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def learn_from_ratings(self) -> None:
        """Rebuild all internal preference state from the ratings table."""
        if self.store.rating_count() < self.min_ratings:
            self._profile_vec.clear()
            self._category_scores.clear()
            self._source_scores.clear()
            return

        rows = list(
            self.store.db.query(
                "SELECT r.rating, r.rated_at, a.title, a.content,"
                "       a.category, a.source"
                " FROM ratings r"
                " JOIN articles a ON a.url = r.url",
            ),
        )

        self._liked_terms.clear()
        self._disliked_terms.clear()
        self._profile_vec.clear()

        now = datetime.now(UTC)
        lam = math.log(2) / self.decay_half_life_days

        # Accumulators for category and source weighted sums.
        cat_sum: dict[str, float] = {}
        cat_weight_sum: dict[str, float] = {}
        src_sum: dict[str, float] = {}
        src_weight_sum: dict[str, float] = {}

        for row in rows:
            rating = int(row["rating"])
            decay = _time_decay(str(row.get("rated_at") or ""), now, lam)

            # ---- Term profile -----------------------------------------
            blob = f"{row['title']} {row['content']}"
            terms = _tokenize(blob)
            vec = _term_counts(blob)

            if rating >= 4:
                for t in terms:
                    self._liked_terms[t] += decay
                for t, c in vec.items():
                    self._profile_vec[t] += c * decay
            elif rating <= 2:
                for t in terms:
                    self._disliked_terms[t] += decay
                for t, c in vec.items():
                    self._profile_vec[t] -= 0.5 * c * decay

            # ---- Category aggregation ---------------------------------
            cat = str(row.get("category") or "").strip()
            if cat:
                cat_sum[cat] = cat_sum.get(cat, 0.0) + rating * decay
                cat_weight_sum[cat] = cat_weight_sum.get(cat, 0.0) + decay

            # ---- Source aggregation -----------------------------------
            src = str(row.get("source") or "").strip()
            if src:
                src_sum[src] = src_sum.get(src, 0.0) + rating * decay
                src_weight_sum[src] = src_weight_sum.get(src, 0.0) + decay

        # Convert weighted sums to mean-minus-midpoint scores.
        self._category_scores = {
            cat: (cat_sum[cat] / cat_weight_sum[cat]) - 3.0
            for cat in cat_sum
            if cat_weight_sum.get(cat, 0) > 0
        }
        self._source_scores = {
            src: (src_sum[src] / src_weight_sum[src]) - 3.0
            for src in src_sum
            if src_weight_sum.get(src, 0) > 0
        }

    def rank_articles(
        self,
        articles: list[dict[str, Any]],
        keyword_high: set[str] | None = None,
        keyword_medium: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return ``articles`` sorted by preference score (highest first)."""
        self.learn_from_ratings()
        high = keyword_high or set()
        medium = keyword_medium or set()
        prof_norm = _counter_norm(self._profile_vec)

        scored: list[tuple[float, dict[str, Any]]] = []
        for art in articles:
            text = (
                f"{art.get('title', '')} {art.get('content', '')}".lower()
            )
            score = 0.0

            # 1. Keyword boosts.
            for kw in high:
                if kw in text:
                    score += 2.0
            for kw in medium:
                if kw in text:
                    score += 1.0

            # 2. Term-overlap with liked/disliked vocabulary (top 40 terms).
            for term, count in self._liked_terms.most_common(40):
                if term in text:
                    score += 0.15 * min(count, 5)
            for term, count in self._disliked_terms.most_common(40):
                if term in text:
                    score -= 0.2 * min(count, 5)

            # 3. TF-IDF cosine similarity to the profile vector.
            if self.tfidf_weight > 0 and prof_norm > 0 and self._profile_vec:
                avec = _term_counts(
                    f"{art.get('title', '')} {art.get('content', '')}",
                )
                cos = _cosine(avec, self._profile_vec, prof_norm)
                score += self.tfidf_weight * cos

            # 4. Category preference score.
            cat = str(art.get("category") or "").strip()
            if cat and cat in self._category_scores and self.category_weight:
                score += self.category_weight * self._category_scores[cat]

            # 5. Source preference score.
            src = str(art.get("source") or "").strip()
            if src and src in self._source_scores and self.source_weight:
                score += self.source_weight * self._source_scores[src]

            art = {**art, "preference_score": round(score, 3)}
            scored.append((score, art))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored]

    def profile_summary(self) -> dict[str, Any]:
        """Return a human-readable snapshot of the learned preference profile.

        Useful for the ``GET /api/preferences/profile`` endpoint and the UI
        Preferences card, so you can verify the engine is learning correctly.
        """
        self.learn_from_ratings()

        # Pull first/last rating date from the DB.
        earliest = ""
        latest_date = ""
        if self.store.rating_count() > 0:
            rows = list(
                self.store.db.query(
                    "SELECT MIN(rated_at) AS earliest, MAX(rated_at) AS latest"
                    " FROM ratings",
                ),
            )
            if rows:
                earliest = str(rows[0].get("earliest") or "")[:19]
                latest_date = str(rows[0].get("latest") or "")[:19]

        return {
            "rating_count": self.store.rating_count(),
            "earliest_rating": earliest,
            "latest_rating": latest_date,
            "min_ratings_threshold": self.min_ratings,
            "learning_active": self.store.rating_count() >= self.min_ratings,
            "top_liked_terms": [
                {"term": t, "score": round(float(c), 2)}
                for t, c in self._liked_terms.most_common(10)
            ],
            "top_disliked_terms": [
                {"term": t, "score": round(float(c), 2)}
                for t, c in self._disliked_terms.most_common(10)
            ],
            "category_preferences": [
                {"category": cat, "score": round(sc, 3)}
                for cat, sc in sorted(
                    self._category_scores.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ],
            "source_preferences": [
                {"source": src, "score": round(sc, 3)}
                for src, sc in sorted(
                    self._source_scores.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _time_decay(rated_at: str, now: datetime, lam: float) -> float:
    """Return exp(-lam * days_since_rating), clamped to (0, 1].

    Falls back to 1.0 (no decay) when ``rated_at`` cannot be parsed.
    """
    if not rated_at:
        return 1.0
    try:
        ts = datetime.fromisoformat(rated_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        days = max(0.0, (now - ts).total_seconds() / 86400.0)
        return math.exp(-lam * days)
    except (ValueError, OverflowError):
        return 1.0


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{4,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _term_counts(text: str) -> Counter[str]:
    c: Counter[str] = Counter()
    for t in _tokenize(text):
        c[t] += 1
    return c


def _counter_norm(c: Counter[str]) -> float:
    return math.sqrt(sum(v * v for v in c.values()))


def _cosine(a: Counter[str], b: Counter[str], b_norm: float) -> float:
    if not a or not b or b_norm <= 0:
        return 0.0
    dot = 0.0
    for term, av in a.items():
        bv = b.get(term)
        if bv:
            dot += av * bv
    an = _counter_norm(a)
    if an <= 0:
        return 0.0
    return dot / (an * b_norm)
