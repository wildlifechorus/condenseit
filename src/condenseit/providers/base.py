"""LLM provider abstraction."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from typing_extensions import TypedDict


class ArticleSummary(TypedDict):
    """Structured output from a single article summarization call."""

    tldr: str
    key_takeaways: list[str]
    summary: str


# Matches an optional ```json ... ``` or ``` ... ``` fence around JSON.
_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)

# Greedily matches the outermost {...} object in a raw response.
_BRACE_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_summary_response(raw: str) -> ArticleSummary:
    """Parse a JSON article-summary response produced by an LLM.

    Attempts several strategies in order:
      1. Strip whitespace and parse as bare JSON.
      2. Extract JSON from a markdown code fence.
      3. Grab the first ``{...}`` substring and parse it.
      4. Fall back: treat the whole response as the ``summary`` field.

    Always returns a fully-populated :class:`ArticleSummary` dict.
    """
    text = (raw or "").strip()

    candidates: list[str] = [
        text,
        text.rstrip(",") + "}",
        text + "}",
    ]
    # Code-fence extraction
    m = _FENCE_RE.search(text)
    if m:
        chunk = m.group(1).strip()
        candidates = [chunk, chunk.rstrip(",") + "}", chunk + "}"] + candidates
    # Raw brace extraction (broader, try last)
    m2 = _BRACE_RE.search(text)
    if m2:
        chunk2 = m2.group(0)
        candidates += [chunk2, chunk2.rstrip(",") + "}", chunk2 + "}"]

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                continue
            takeaways = data.get("key_takeaways", [])
            if isinstance(takeaways, str):
                # Some models return a newline-separated string instead of an array.
                takeaways = [t.strip() for t in takeaways.splitlines() if t.strip()]
            elif not isinstance(takeaways, list):
                takeaways = []
            return ArticleSummary(
                tldr=str(data.get("tldr", "") or "").strip(),
                key_takeaways=[str(t) for t in takeaways if t],
                summary=str(data.get("summary", "") or "").strip(),
            )
        except (json.JSONDecodeError, ValueError):
            continue

    # Final fallback: treat the whole text as a plain summary.
    return ArticleSummary(tldr="", key_takeaways=[], summary=text)


class SummarizerProvider(ABC):
    @abstractmethod
    def summarize_article(self, article: dict[str, Any]) -> ArticleSummary:
        pass

    @abstractmethod
    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        pass

    @property
    def model_name(self) -> str:
        return "unknown"
