"""LLM-based article reranker (Phase 3).

After classical + embedding scoring, a single cheap LLM call reorders the
top-K candidates using a compact reader profile narrative. The LLM score is
blended with the classical score so a bad LLM response cannot completely
override sane defaults.

Cost: ~1 call per digest run, ~5K tokens in / ~500 out.
Recommended model: qwen/qwen3.5-flash-02-23 (~$0.001/digest run on OpenRouter).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from condenseit.learning.preference_engine import PreferenceEngine
    from condenseit.providers.budget import BudgetTracker

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(\[.*?\])\s*```", re.DOTALL | re.IGNORECASE)
_BRACKET_RE = re.compile(r"\[.*\]", re.DOTALL)
# Reasoning models (Qwen3, DeepSeek-R1, etc.) emit <think>...</think> before output.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


# ---------------------------------------------------------------------------
# Profile narrative
# ---------------------------------------------------------------------------


def build_profile_narrative(engine: PreferenceEngine) -> str:
    """Build a compact plain-text reader profile from learned preferences.

    Keeps output under ~300 tokens so it fits cheaply in every prompt.
    Returns an empty string when the profile is not yet active.
    """
    engine.learn_from_ratings()


    liked_terms = [t for t, _ in engine._liked_terms.most_common(10)]
    disliked_terms = [t for t, _ in engine._disliked_terms.most_common(8)]
    liked_cats = sorted(
        ((c, s) for c, s in engine._category_scores.items() if s > 0.3),
        key=lambda x: x[1],
        reverse=True,
    )[:4]
    disliked_cats = sorted(
        ((c, s) for c, s in engine._category_scores.items() if s < -0.3),
        key=lambda x: x[1],
    )[:3]
    liked_srcs = sorted(
        ((s, v) for s, v in engine._source_scores.items() if v > 0.5),
        key=lambda x: x[1],
        reverse=True,
    )[:3]
    disliked_srcs = sorted(
        ((s, v) for s, v in engine._source_scores.items() if v < -0.5),
        key=lambda x: x[1],
    )[:3]

    parts: list[str] = []
    if liked_terms:
        parts.append(f"Likes: {', '.join(liked_terms)}")
    if disliked_terms:
        parts.append(f"Dislikes: {', '.join(disliked_terms)}")
    if liked_cats:
        cats_str = ", ".join(f"{c} (+{s:.1f})" for c, s in liked_cats)
        parts.append(f"Preferred categories: {cats_str}")
    if disliked_cats:
        cats_str = ", ".join(f"{c} ({s:.1f})" for c, s in disliked_cats)
        parts.append(f"Avoided categories: {cats_str}")
    if liked_srcs:
        parts.append(f"Liked sources: {', '.join(s for s, _ in liked_srcs)}")
    if disliked_srcs:
        parts.append(f"Disliked sources: {', '.join(s for s, _ in disliked_srcs)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------


def _build_rerank_prompt(
    candidates: list[dict[str, Any]], profile: str
) -> str:
    articles_json = json.dumps(
        [
            {
                "url": str(a.get("url", "")),
                "title": str(a.get("title", "")),
                "category": str(a.get("category", "")),
                "source": str(a.get("source", "")),
                "snippet": str(a.get("content") or "")[:200],
            }
            for a in candidates
        ],
        ensure_ascii=False,
    )
    return (
        "You are a news relevance ranker. Given a reader profile and a list of "
        "articles, return ONLY a JSON array where each element has:\n"
        '  {"url": "<article url>", "relevance": <float 0.0-1.0>, "reason": "<5 words max>"}\n\n'  # noqa: E501
        f"Reader profile:\n{profile}\n\n"
        f"Articles:\n{articles_json}\n\n"
        "JSON array (one entry per article, same length as input):"
    )


def _parse_rerank_response(raw: str) -> dict[str, tuple[float, str]]:
    """Parse the LLM rerank response into a {url: (relevance, reason)} map."""
    # Strip reasoning-model thinking blocks before any JSON search.
    text = _THINK_RE.sub("", raw or "").strip()

    candidates: list[str] = [text]
    m = _FENCE_RE.search(text)
    if m:
        candidates.insert(0, m.group(1))
    m2 = _BRACKET_RE.search(text)
    if m2:
        candidates.append(m2.group(0))
    # Partial-JSON fallback: if the response was truncated before the closing
    # bracket (max_tokens hit), close the array and try to parse what we have.
    if text.startswith("[") and not text.rstrip().endswith("]"):
        # Strip the last (incomplete) item and close the array.
        last_complete = text.rfind("},")
        if last_complete != -1:
            candidates.append(text[: last_complete + 1] + "]")

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if not isinstance(data, list):
                continue
            result: dict[str, tuple[float, str]] = {}
            for item in data:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url", "")).strip()
                if not url:
                    continue
                try:
                    rel = max(0.0, min(1.0, float(item.get("relevance", 0.5) or 0.5)))
                except (TypeError, ValueError):
                    rel = 0.5
                reason = str(item.get("reason", "") or "").strip()[:200]
                result[url] = (rel, reason)
            if result:
                return result
        except (json.JSONDecodeError, ValueError):
            continue

    return {}


def _call_openrouter(
    prompt: str,
    model: str,
    api_key: str,
    budget: BudgetTracker | None = None,
) -> str:
    import httpx

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a relevance ranker. Respond ONLY with a JSON array. "
                    "No markdown, no code fences, no extra text, no thinking."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2500,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/condenseit/condenseit",
        "X-Title": "CondenseIt",
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    if budget is not None:
        usage = data.get("usage") or {}
        cost = float(usage.get("cost", 0) or 0)
        if cost > 0:
            budget.record_spend(
                cost, model=model, tokens=int(usage.get("total_tokens", 0) or 0)
            )
    choices = data.get("choices") or []
    if not choices:
        return ""
    content = str(choices[0]["message"]["content"]).strip()
    # Some OpenRouter models expose reasoning in a separate field; strip it.
    reasoning = choices[0].get("message", {}).get("reasoning", "") or ""
    if reasoning:
        # Only keep content that is not just the reasoning repeated.
        content = content.replace(reasoning.strip(), "").strip()
    return content


def _call_openai_compat(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str = "",
) -> str:
    """Call any OpenAI-compatible /chat/completions endpoint for reranking."""
    import httpx

    base_url = base_url.rstrip("/")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a relevance ranker. Respond ONLY with a JSON array. "
                    "No markdown, no code fences, no extra text, no thinking."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 2500,
    }
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    return str(choices[0]["message"]["content"]).strip()


def _call_ollama(prompt: str, model: str, host: str) -> str:
    import httpx

    host = host.rstrip("/")
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.1, "num_predict": 2500},
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return str(data.get("response", "")).strip()


def rerank(
    articles: list[dict[str, Any]],
    profile_narrative: str,
    *,
    model: str,
    api_key: str | None = None,
    ollama_host: str | None = None,
    openai_base_url: str | None = None,
    openai_api_key: str = "",
    top_k: int = 30,
    blend: float = 0.4,
    budget: BudgetTracker | None = None,
) -> list[dict[str, Any]]:
    """Reorder articles using a single LLM call, blending LLM scores with classical.

    Returns the full list with LLM-blended ``preference_score`` values and
    ``llm_rerank`` / ``llm_reason`` keys added to ``score_breakdown``.
    Fails silently (original order preserved) when the LLM call or parse fails.

    Provider selection order: OpenRouter (api_key) → OpenAI-compat
    (openai_base_url) → Ollama (ollama_host).
    """
    if not articles or not profile_narrative:
        return articles

    candidates = articles[:top_k]
    rest = articles[top_k:]

    prompt = _build_rerank_prompt(candidates, profile_narrative)

    try:
        if api_key:
            raw = _call_openrouter(prompt, model, api_key, budget=budget)
        elif openai_base_url:
            raw = _call_openai_compat(
                prompt, model, openai_base_url, api_key=openai_api_key
            )
        elif ollama_host:
            raw = _call_ollama(prompt, model, ollama_host)
        else:
            return articles

        scores = _parse_rerank_response(raw)
        if not scores:
            logger.warning(
                "Reranker returned empty/unparseable response; skipping. "
                "Raw response (first 500 chars): %r",
                raw[:500],
            )
            return articles

        reranked = _apply_blend(candidates, scores, blend)
        reranked.sort(key=lambda a: a.get("preference_score", 0.0), reverse=True)
        return reranked + rest

    except Exception as exc:
        logger.warning("Reranker failed, using original order: %s", exc)
        return articles


def _apply_blend(
    candidates: list[dict[str, Any]],
    scores: dict[str, tuple[float, str]],
    blend: float,
) -> list[dict[str, Any]]:
    """Merge LLM relevance scores into each article's preference_score."""
    result = []
    for art in candidates:
        url = str(art.get("url", ""))
        classical = float(art.get("preference_score", 0.0))
        llm_rel, reason = scores.get(url, (0.5, ""))
        blended = (1.0 - blend) * classical + blend * llm_rel
        bd = dict(art.get("score_breakdown") or {})
        bd["llm_rerank"] = round(blend * llm_rel, 3)
        bd["llm_reason"] = reason
        art = {
            **art,
            "preference_score": round(blended, 3),
            "score_breakdown": bd,
        }
        result.append(art)
    return result
