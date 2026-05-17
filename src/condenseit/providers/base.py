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

# Detects the start of a Chinese LLM refusal phrase that some multilingual
# models append mid-response (e.g. "作为一个人工智能语言模型...").
# We strip from the first run of consecutive CJK characters onward when that
# run comprises the majority of the remaining text, so we don't accidentally
# truncate article titles that legitimately contain a single CJK character.
_CJK_BLOCK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]{4,}")


def _strip_non_latin_tail(value: str) -> str:
    """Remove a trailing CJK/non-Latin injection appended by the LLM.

    Some cheap multilingual models start answering in English, then switch
    to a Chinese refusal phrase mid-field.  This function finds the earliest
    CJK run that makes up more than 30 % of the remaining text and truncates
    there, returning a clean Latin-script prefix.
    """
    for m in _CJK_BLOCK_RE.finditer(value):
        tail = value[m.start():]
        non_ascii_in_tail = sum(1 for c in tail if ord(c) > 127)
        if len(tail) > 0 and non_ascii_in_tail / len(tail) > 0.3:
            return value[: m.start()].rstrip()
    return value


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
                tldr=_strip_non_latin_tail(
                    str(data.get("tldr", "") or "").strip()
                ),
                key_takeaways=[
                    _strip_non_latin_tail(str(t))
                    for t in takeaways
                    if t
                ],
                summary=_strip_non_latin_tail(
                    str(data.get("summary", "") or "").strip()
                ),
            )
        except (json.JSONDecodeError, ValueError):
            continue

    # Final fallback: treat the whole text as a plain summary, but only when
    # it looks like Latin-script prose. If most characters are non-ASCII (e.g.
    # a Chinese refusal phrase from a multilingual model), discard the response
    # to avoid showing garbage text in the UI.
    if text:
        non_ascii = sum(1 for c in text if ord(c) > 127)
        if non_ascii / len(text) > 0.2:
            return ArticleSummary(tldr="", key_takeaways=[], summary="")
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
