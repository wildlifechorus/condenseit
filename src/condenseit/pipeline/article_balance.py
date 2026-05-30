"""Pick digest articles with at least one slot per category when possible."""

from collections import defaultdict, deque
from typing import Any


def select_balanced_digest_articles(
    ranked: list[dict[str, Any]],
    max_n: int,
    max_per_category: int = 5,
) -> list[dict[str, Any]]:
    """Return up to ``max_n`` articles, preferring category coverage.

    Phase 1 walks categories in first-appearance order (by global rank) and
    takes the highest-ranked not-yet-chosen article from each category.

    Phase 2 walks the full global rank list and fills remaining slots, capping
    any single category at ``max_per_category`` articles.

    Categories with no candidates in ``ranked`` are omitted. If ``max_n`` is
    smaller than the number of distinct categories, only the first
    ``max_n`` categories (by first appearance) receive a guaranteed slot.
    """
    if max_n <= 0:
        return []
    if not ranked:
        return []

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

    for cat in category_order:
        if len(selected) >= max_n:
            break
        taken = take_next_for_category(cat)
        if taken is not None:
            selected.append(taken)
            per_category_count[cat] += 1

    for art in ranked:
        if len(selected) >= max_n:
            break
        url = str(art.get("url") or "")
        if not url or url in chosen_urls:
            continue
        cat = str(art.get("category") or "General").strip() or "General"
        if per_category_count[cat] >= max_per_category:
            continue
        chosen_urls.add(url)
        per_category_count[cat] += 1
        selected.append(art)

    return selected
