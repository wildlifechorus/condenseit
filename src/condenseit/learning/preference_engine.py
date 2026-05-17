"""Rating-based article ranking with category/source preferences and time decay.

Scoring tiers (all additive):
  1. Keyword boost       - configured high/medium keywords from config.yaml
  2. Term overlap        - liked/disliked terms from past rated articles
  3. Bigram overlap      - title bigrams from past rated articles
  4. TF-IDF cosine       - cosine similarity to the explicit ratings profile
  5. Category score      - mean rating per category minus 3.0 (neutral midpoint)
  6. Source score        - mean rating per feed/source minus 3.0
  7. Implicit signals    - read (+mild), read-later (+strong), dismissed (-mild)
     broken down as implicit_category, implicit_source, implicit_content
  8. Synonym boost       - propagates profile weight across synonym groups

All rating rows are weighted by exponential time decay so recent tastes
matter more than stale ones. Decay factor: exp(-ln(2)/half_life * days).

Implicit signals use the same decay but are scaled by `implicit_signal_weight`
(default 0.5) so explicit star ratings always dominate.
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
        # 3-letter common words (newly included since min token length dropped to 3)
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
        "has", "him", "his", "its", "may", "nor", "now", "one", "our", "out",
        "own", "per", "run", "see", "set", "she", "sit", "six", "ten", "too",
        "two", "use", "was", "way", "who", "why", "yet", "ago", "any", "big",
        "bit", "day", "did", "end", "far", "few", "get", "got", "how", "job",
        "key", "let", "lot", "low", "man", "met", "new", "old", "put", "say",
        "via", "web", "app", "add", "fix", "run", "bug", "log", "set", "off",
        "try", "top", "sub", "hit", "put", "ask", "buy", "cut", "due", "era",
        "fly", "gap", "gen", "lot", "map", "mix", "now", "opt", "pop", "raw",
        "red", "row", "tip", "tri", "url", "way", "win", "yes", "yet",
        # 4-letter+ generic connectives
        "that", "this", "with", "from", "have", "will", "your", "about",
        "into", "than", "been", "also", "more", "just", "some", "like",
        "over", "when", "only", "most", "very", "after", "other", "which",
        "these", "those", "their", "would", "could", "should", "first",
        "there", "then", "each", "such", "both", "even", "back", "well",
        "what", "where", "here", "make", "made", "come", "know", "take",
        "time", "year", "week", "month", "many", "last", "next",
        # Tech-digest filler
        "article", "update", "release", "using", "https", "http", "news",
        "read", "version", "post", "blog", "link", "share", "learn", "find",
        "help", "need", "want", "look", "said", "says", "note", "docs",
        "page", "site", "team", "repo", "code", "data", "user", "tool",
        "type", "list", "example", "based", "added", "fixed", "changed",
        "support", "works", "working", "check", "getting", "please",
        "allows", "without", "between", "through", "including", "following",
        "available", "provides", "requires", "improved",
    },
)


class PreferenceEngine:
    """Learns from star ratings and implicit signals, then ranks articles."""

    def __init__(
        self,
        store: ContentStore,
        min_ratings: int = 5,
        tfidf_weight: float = 0.35,
        category_weight: float = 0.6,
        source_weight: float = 0.3,
        decay_half_life_days: int = 30,
        implicit_signal_weight: float = 0.5,
        topic_synonyms: dict[str, list[str]] | None = None,
    ) -> None:
        self.store = store
        self.min_ratings = min_ratings
        self.tfidf_weight = tfidf_weight
        self.category_weight = category_weight
        self.source_weight = source_weight
        self.decay_half_life_days = max(1, decay_half_life_days)
        self.implicit_signal_weight = max(0.0, min(1.0, implicit_signal_weight))

        # Build a flat synonym map: each term -> set of synonyms (including itself).
        # All lookups are lowercase.
        raw_synonyms = topic_synonyms or {}
        self._synonym_map: dict[str, list[str]] = {}
        for _group_label, members in raw_synonyms.items():
            lc = [m.lower().strip() for m in members if m.strip()]
            for term in lc:
                others = [m for m in lc if m != term]
                if others:
                    self._synonym_map.setdefault(term, []).extend(others)

        # --- Explicit ratings profile (from star ratings) ---
        self._liked_terms: Counter[str] = Counter()
        self._disliked_terms: Counter[str] = Counter()
        self._liked_bigrams: Counter[str] = Counter()
        self._disliked_bigrams: Counter[str] = Counter()
        self._profile_vec: Counter[str] = Counter()
        self._category_scores: dict[str, float] = {}
        self._source_scores: dict[str, float] = {}

        # --- Implicit signals profile (from read/saved/dismissed) ---
        self._implicit_liked_terms: Counter[str] = Counter()
        self._implicit_disliked_terms: Counter[str] = Counter()
        self._implicit_profile_vec: Counter[str] = Counter()
        self._implicit_category_scores: dict[str, float] = {}
        self._implicit_source_scores: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def learn_from_ratings(self) -> None:
        """Rebuild all internal preference state from the ratings table."""
        self._clear_profiles()

        if self.store.rating_count() < self.min_ratings:
            return

        rows = list(
            self.store.db.query(
                "SELECT r.rating, r.rated_at, a.title, a.content,"
                "       a.category, a.source"
                " FROM ratings r"
                " JOIN articles a ON a.url = r.url",
            ),
        )

        now = datetime.now(UTC)
        lam = math.log(2) / self.decay_half_life_days

        cat_sum: dict[str, float] = {}
        cat_weight_sum: dict[str, float] = {}
        src_sum: dict[str, float] = {}
        src_weight_sum: dict[str, float] = {}

        for row in rows:
            rating = int(row["rating"])
            decay = _time_decay(str(row.get("rated_at") or ""), now, lam)

            blob = f"{row['title']} {row['content']}"
            terms = _tokenize(blob)
            title_bigrams = _bigrams(str(row["title"]))
            vec = _term_counts(blob)

            if rating >= 4:
                for t in terms:
                    self._liked_terms[t] += decay
                for bg in title_bigrams:
                    self._liked_bigrams[bg] += decay
                for t, c in vec.items():
                    self._profile_vec[t] += c * decay
            elif rating <= 2:
                for t in terms:
                    self._disliked_terms[t] += decay
                for bg in title_bigrams:
                    self._disliked_bigrams[bg] += decay
                for t, c in vec.items():
                    self._profile_vec[t] -= 0.5 * c * decay

            cat = str(row.get("category") or "").strip()
            if cat:
                cat_sum[cat] = cat_sum.get(cat, 0.0) + rating * decay
                cat_weight_sum[cat] = cat_weight_sum.get(cat, 0.0) + decay

            src = str(row.get("source") or "").strip()
            if src:
                src_sum[src] = src_sum.get(src, 0.0) + rating * decay
                src_weight_sum[src] = src_weight_sum.get(src, 0.0) + decay

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

        # Apply implicit signals on top of explicit profile.
        if self.implicit_signal_weight > 0:
            self._learn_implicit_signals(now, lam)

    def rank_articles(
        self,
        articles: list[dict[str, Any]],
        keyword_high: set[str] | None = None,
        keyword_medium: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return ``articles`` sorted by preference score (highest first).

        Each article dict is augmented with:
          - ``preference_score``: total additive score (float)
          - ``score_breakdown``: per-signal contributions (dict)
        """
        self.learn_from_ratings()
        high = keyword_high or set()
        medium = keyword_medium or set()
        prof_norm = _counter_norm(self._profile_vec)
        implicit_prof_norm = _counter_norm(self._implicit_profile_vec)

        scored: list[tuple[float, dict[str, Any]]] = []
        for art in articles:
            text_lower = (
                f"{art.get('title', '')} {art.get('content', '')}".lower()
            )
            title_lower = str(art.get("title", "")).lower()
            article_tokens = set(_tokenize(text_lower))
            article_bigrams_list = _bigrams(title_lower)
            article_bigrams = set(article_bigrams_list)

            breakdown: dict[str, float] = {
                "keyword_high": 0.0,
                "keyword_medium": 0.0,
                "term_overlap": 0.0,
                "bigram_overlap": 0.0,
                "tfidf_cosine": 0.0,
                "category": 0.0,
                "source": 0.0,
                "implicit_content": 0.0,
                "implicit_category": 0.0,
                "implicit_source": 0.0,
                "synonym_boost": 0.0,
            }

            # 1. Keyword boosts from config.
            for kw in high:
                if kw in text_lower:
                    breakdown["keyword_high"] += 2.0
            for kw in medium:
                if kw in text_lower:
                    breakdown["keyword_medium"] += 1.0

            # 2. Synonym expansion: expand article tokens to include synonyms
            # so profile weight learned on one term applies to related terms.
            expanded_tokens = set(article_tokens)
            syn_score = 0.0
            for tok in article_tokens:
                for syn in self._synonym_map.get(tok, []):
                    if syn not in article_tokens:
                        expanded_tokens.add(syn)
                        # Bonus for synonym matches from explicit liked terms.
                        liked_w = self._liked_terms.get(syn, 0.0)
                        disliked_w = self._disliked_terms.get(syn, 0.0)
                        if liked_w > 0:
                            syn_score += 0.08 * min(liked_w, 5)
                        if disliked_w > 0:
                            syn_score -= 0.10 * min(disliked_w, 5)
            breakdown["synonym_boost"] = round(syn_score, 3)

            # 3. Term overlap with liked/disliked vocabulary (top 50 terms).
            term_score = 0.0
            for term, count in self._liked_terms.most_common(50):
                if term in expanded_tokens:
                    term_score += 0.15 * min(count, 5)
            for term, count in self._disliked_terms.most_common(50):
                if term in expanded_tokens:
                    term_score -= 0.2 * min(count, 5)
            breakdown["term_overlap"] = round(term_score, 3)

            # 4. Bigram overlap with liked/disliked title bigrams (top 30).
            bigram_score = 0.0
            for bg, count in self._liked_bigrams.most_common(30):
                if bg in article_bigrams:
                    bigram_score += 0.25 * min(count, 5)
            for bg, count in self._disliked_bigrams.most_common(30):
                if bg in article_bigrams:
                    bigram_score -= 0.3 * min(count, 5)
            breakdown["bigram_overlap"] = round(bigram_score, 3)

            # 5. TF-IDF cosine similarity to the explicit ratings profile.
            if self.tfidf_weight > 0 and prof_norm > 0 and self._profile_vec:
                avec = _term_counts(
                    f"{art.get('title', '')} {art.get('content', '')}",
                )
                cos = _cosine(avec, self._profile_vec, prof_norm)
                breakdown["tfidf_cosine"] = round(self.tfidf_weight * cos, 3)

            # 6. Category preference (explicit ratings).
            cat = str(art.get("category") or "").strip()
            if cat and cat in self._category_scores and self.category_weight:
                breakdown["category"] = round(
                    self.category_weight * self._category_scores[cat], 3
                )

            # 7. Source preference (explicit ratings).
            src = str(art.get("source") or "").strip()
            if src and src in self._source_scores and self.source_weight:
                breakdown["source"] = round(
                    self.source_weight * self._source_scores[src], 3
                )

            # 8. Implicit signals (read/saved/dismissed contributions).
            if self.implicit_signal_weight > 0:
                # Implicit content (term + TF-IDF from implicit profile).
                imp_term = 0.0
                for term, count in self._implicit_liked_terms.most_common(50):
                    if term in expanded_tokens:
                        imp_term += 0.15 * min(count, 5)
                for term, count in self._implicit_disliked_terms.most_common(
                    50
                ):
                    if term in expanded_tokens:
                        imp_term -= 0.2 * min(count, 5)
                if (
                    self.tfidf_weight > 0
                    and implicit_prof_norm > 0
                    and self._implicit_profile_vec
                ):
                    avec = _term_counts(
                        f"{art.get('title', '')} {art.get('content', '')}",
                    )
                    imp_cos = _cosine(
                        avec, self._implicit_profile_vec, implicit_prof_norm
                    )
                    imp_term += self.tfidf_weight * imp_cos
                breakdown["implicit_content"] = round(
                    self.implicit_signal_weight * imp_term, 3
                )

                # Implicit category preference.
                if (
                    cat
                    and cat in self._implicit_category_scores
                    and self.category_weight
                ):
                    breakdown["implicit_category"] = round(
                        self.implicit_signal_weight
                        * self.category_weight
                        * self._implicit_category_scores[cat],
                        3,
                    )

                # Implicit source preference.
                if (
                    src
                    and src in self._implicit_source_scores
                    and self.source_weight
                ):
                    breakdown["implicit_source"] = round(
                        self.implicit_signal_weight
                        * self.source_weight
                        * self._implicit_source_scores[src],
                        3,
                    )

            total = sum(breakdown.values())
            art = {
                **art,
                "preference_score": round(total, 3),
                "score_breakdown": breakdown,
            }
            scored.append((total, art))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored]

    def profile_summary(self) -> dict[str, Any]:
        """Return a human-readable snapshot of the learned preference profile.

        Used by the ``GET /api/preferences/profile`` endpoint and the
        Preferences page in the admin UI.
        """
        self.learn_from_ratings()

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

        # Rating distribution (count of each star level).
        rating_distribution: dict[str, int] = {
            "1": 0, "2": 0, "3": 0, "4": 0, "5": 0,
        }
        if self.store.rating_count() > 0:
            for dist_row in self.store.db.query(
                "SELECT rating, COUNT(*) as cnt FROM ratings GROUP BY rating"
            ):
                star = str(int(dist_row["rating"]))
                if star in rating_distribution:
                    rating_distribution[star] = int(dist_row["cnt"])

        # Implicit signal counts.
        read_count = 0
        saved_count = 0
        dismissed_count = 0
        if "read_articles" in self.store.db.table_names():
            try:
                read_count = self.store.db["read_articles"].count
            except Exception:
                pass
        if "read_later" in self.store.db.table_names():
            try:
                saved_count = self.store.db["read_later"].count
            except Exception:
                pass
        dismissed_count = self.store.dismissed_count()

        # Decay weight for oldest rating (for transparency in the UI).
        oldest_rating_decay = 1.0
        if earliest:
            lam = math.log(2) / self.decay_half_life_days
            oldest_rating_decay = round(
                _time_decay(earliest, datetime.now(UTC), lam), 3
            )

        return {
            "rating_count": self.store.rating_count(),
            "earliest_rating": earliest,
            "latest_rating": latest_date,
            "min_ratings_threshold": self.min_ratings,
            "learning_active": self.store.rating_count() >= self.min_ratings,
            "rating_distribution": rating_distribution,
            "implicit_read_count": read_count,
            "implicit_saved_count": saved_count,
            "implicit_dismissed_count": dismissed_count,
            "implicit_learning_active": self.implicit_signal_weight > 0,
            "oldest_rating_decay": oldest_rating_decay,
            "decay_half_life_days": self.decay_half_life_days,
            "top_liked_terms": [
                {"term": t, "score": round(float(c), 2)}
                for t, c in self._liked_terms.most_common(15)
            ],
            "top_disliked_terms": [
                {"term": t, "score": round(float(c), 2)}
                for t, c in self._disliked_terms.most_common(15)
            ],
            "top_liked_bigrams": [
                {"term": bg, "score": round(float(c), 2)}
                for bg, c in self._liked_bigrams.most_common(10)
            ],
            "top_disliked_bigrams": [
                {"term": bg, "score": round(float(c), 2)}
                for bg, c in self._disliked_bigrams.most_common(10)
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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clear_profiles(self) -> None:
        """Reset all in-memory profile state."""
        self._liked_terms.clear()
        self._disliked_terms.clear()
        self._liked_bigrams.clear()
        self._disliked_bigrams.clear()
        self._profile_vec.clear()
        self._category_scores.clear()
        self._source_scores.clear()
        self._implicit_liked_terms.clear()
        self._implicit_disliked_terms.clear()
        self._implicit_profile_vec.clear()
        self._implicit_category_scores.clear()
        self._implicit_source_scores.clear()

    def _learn_implicit_signals(self, now: datetime, lam: float) -> None:
        """Augment the profile with implicit engagement signals.

        Signal strengths (as virtual star-rating equivalents):
          - Read articles:    3.8 stars (mildly positive)
          - Saved for later:  4.5 stars (strong interest)
          - Dismissed:        1.5 stars (mild disinterest)

        All contributions are scaled by ``implicit_signal_weight`` so explicit
        star ratings always dominate the final profile.
        """
        imp_cat_sum: dict[str, float] = {}
        imp_cat_w: dict[str, float] = {}
        imp_src_sum: dict[str, float] = {}
        imp_src_w: dict[str, float] = {}

        def _accumulate(
            rows: list[dict[str, Any]],
            ts_key: str,
            virtual_rating: float,
            liked: bool,
        ) -> None:
            for row in rows:
                decay = _time_decay(str(row.get(ts_key) or ""), now, lam)
                blob = f"{row.get('title', '')} {row.get('content', '')}"
                terms = _tokenize(blob)
                vec = _term_counts(blob)

                if liked:
                    for t in terms:
                        self._implicit_liked_terms[t] += decay
                    for t, c in vec.items():
                        self._implicit_profile_vec[t] += c * decay
                else:
                    for t in terms:
                        self._implicit_disliked_terms[t] += decay
                    for t, c in vec.items():
                        self._implicit_profile_vec[t] -= 0.5 * c * decay

                cat = str(row.get("category") or "").strip()
                if cat:
                    imp_cat_sum[cat] = (
                        imp_cat_sum.get(cat, 0.0) + virtual_rating * decay
                    )
                    imp_cat_w[cat] = imp_cat_w.get(cat, 0.0) + decay

                src = str(row.get("source") or "").strip()
                if src:
                    imp_src_sum[src] = (
                        imp_src_sum.get(src, 0.0) + virtual_rating * decay
                    )
                    imp_src_w[src] = imp_src_w.get(src, 0.0) + decay

        # Read articles: mild positive signal (virtual rating 3.8).
        if "read_articles" in self.store.db.table_names():
            try:
                read_rows = list(
                    self.store.db.query(
                        "SELECT ra.url, ra.read_at as ts, a.title, a.content,"
                        "       a.category, a.source"
                        " FROM read_articles ra"
                        " JOIN articles a ON a.url = ra.url",
                    )
                )
                _accumulate(read_rows, "ts", 3.8, liked=True)
            except Exception:
                pass

        # Saved for later: strong positive signal (virtual rating 4.5).
        if "read_later" in self.store.db.table_names():
            try:
                saved_rows = list(
                    self.store.db.query(
                        "SELECT rl.url, rl.saved_at as ts, rl.title,"
                        "       rl.summary as content, rl.category, rl.source"
                        " FROM read_later rl",
                    )
                )
                _accumulate(saved_rows, "ts", 4.5, liked=True)
            except Exception:
                pass

        # Dismissed: mild negative signal (virtual rating 1.5).
        if "dismissed_articles" in self.store.db.table_names():
            try:
                dismissed_rows = list(
                    self.store.db.query(
                        "SELECT da.url, da.dismissed_at as ts,"
                        "       a.title, a.content, a.category, a.source"
                        " FROM dismissed_articles da"
                        " JOIN articles a ON a.url = da.url",
                    )
                )
                _accumulate(dismissed_rows, "ts", 1.5, liked=False)
            except Exception:
                pass

        # Convert implicit weighted sums to mean-minus-midpoint scores.
        self._implicit_category_scores = {
            cat: (imp_cat_sum[cat] / imp_cat_w[cat]) - 3.0
            for cat in imp_cat_sum
            if imp_cat_w.get(cat, 0) > 0
        }
        self._implicit_source_scores = {
            src: (imp_src_sum[src] / imp_src_w[src]) - 3.0
            for src in imp_src_sum
            if imp_src_w.get(src, 0) > 0
        }


# ---------------------------------------------------------------------------
# Module-level helpers
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
    """Extract meaningful word tokens (length >= 3) from text."""
    words = re.findall(r"[a-z0-9]{3,}", text.lower())
    return [w for w in words if w not in _STOP_WORDS]


def _bigrams(title: str) -> list[str]:
    """Extract consecutive word bigrams from a title string.

    Only bigrams where both words pass the stop-word filter and have length
    >= 3 are included, keeping the signal-to-noise ratio high.
    """
    words = re.findall(r"[a-z0-9]{3,}", title.lower())
    filtered = [w for w in words if w not in _STOP_WORDS]
    return [
        f"{filtered[i]} {filtered[i + 1]}"
        for i in range(len(filtered) - 1)
    ]


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
