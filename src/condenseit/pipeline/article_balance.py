"""Pick digest articles with at least one slot per category when possible."""

from collections import defaultdict, deque
from typing import Any


def select_balanced_digest_articles(
    ranked: list[dict[str, Any]],
    max_n: int,
    max_per_category: int = 5,
    *,
    category_scores: dict[str, float] | None = None,
    exclude_threshold: float = -1.5,
    demote_threshold: float = -0.5,
    demote_cap: int = 1,
) -> list[dict[str, Any]]:
    """Return up to ``max_n`` articles, preferring category coverage.

    Phase 1 walks categories in first-appearance order (by global rank) and
    takes the highest-ranked not-yet-chosen article from each category.

    Phase 2 walks the full global rank list and fills remaining slots, capping
    any single category at ``max_per_category`` articles.

    Categories with no candidates in ``ranked`` are omitted. If ``max_n`` is
    smaller than the number of distinct categories, only the first
    ``max_n`` categories (by first appearance) receive a guaranteed slot.

    Negative-preference gate
    ------------------------
    When ``category_scores`` is provided (the learned preference per category,
    in mean-rating-minus-3 units, so positive = liked and negative = disliked),
    categories you consistently dislike are no longer force-included:

    - score <= ``exclude_threshold``: the category is dropped entirely. It
      receives no guaranteed slot and is skipped during fill. This stops
      strongly disliked categories (e.g. a "General News" feed you rate 1 star)
      from claiming digest slots every run just to satisfy "category coverage".
    - ``exclude_threshold`` < score <= ``demote_threshold``: the category is
      demoted. It gets no guaranteed Phase-1 slot and its per-category cap is
      lowered to ``demote_cap`` (default 1), so at most one of its best
      articles can still appear when global rank earns it a fill slot.
    - score > ``demote_threshold`` (or unknown): normal behaviour, with a
      guaranteed slot and the full ``max_per_category`` cap.

    When ``category_scores`` is ``None`` or empty (e.g. learning is not yet
    active), the gate is disabled and behaviour is identical to the classic
    coverage-first selection. As a safety net, if gating would remove every
    article, the top global articles are returned instead so a digest is never
    silently emptied.
    """
    if max_n <= 0:
        return []
    if not ranked:
        return []

    scores = category_scores or {}

    def _category_policy(category: str) -> tuple[bool, int]:
        """Return ``(guaranteed_slot, cap)`` for ``category``.

        ``cap`` of 0 means the category is excluded entirely.
        """
        if not scores:
            return True, max_per_category
        score = scores.get(category)
        if score is None:
            return True, max_per_category
        if score <= exclude_threshold:
            return False, 0
        if score <= demote_threshold:
            return False, max(0, min(max_per_category, demote_cap))
        return True, max_per_category

    by_category: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    category_order: list[str] = []
    seen_category: set[str] = set()

    for art in ranked:
        cat = str(art.get("category") or "General").strip() or "General"
        if cat not in seen_category:
            category_order.append(cat)
            seen_category.add(cat)
        by_category[cat].append(art)

    selected: list[dict[str, Any]] = []
    chosen_urls: set[str] = set()
    per_category_count: dict[str, int] = defaultdict(int)
    policy: dict[str, tuple[bool, int]] = {
        cat: _category_policy(cat) for cat in category_order
    }

    def take_next_for_category(category: str) -> dict[str, Any] | None:
        q = by_category[category]
        while q:
            candidate = q.popleft()
            url = str(candidate.get("url") or "")
            if not url or url in chosen_urls:
                continue
            chosen_urls.add(url)
            return candidate
        return None

    # Phase 1: guarantee one slot to each non-demoted, non-excluded category.
    for cat in category_order:
        if len(selected) >= max_n:
            break
        guaranteed, cap = policy[cat]
        if not guaranteed or cap <= 0:
            continue
        taken = take_next_for_category(cat)
        if taken is not None:
            selected.append(taken)
            per_category_count[cat] += 1

    # Phase 2: fill remaining slots by global rank, honouring per-category caps.
    for art in ranked:
        if len(selected) >= max_n:
            break
        url = str(art.get("url") or "")
        if not url or url in chosen_urls:
            continue
        cat = str(art.get("category") or "General").strip() or "General"
        _guaranteed, cap = policy.get(cat, (True, max_per_category))
        if cap <= 0 or per_category_count[cat] >= cap:
            continue
        chosen_urls.add(url)
        per_category_count[cat] += 1
        selected.append(art)

    # Safety net: never return an empty digest purely because of the gate.
    if not selected and scores:
        fallback: list[dict[str, Any]] = []
        seen: set[str] = set()
        for art in ranked:
            url = str(art.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            fallback.append(art)
            if len(fallback) >= max_n:
                break
        return fallback

    return selected
