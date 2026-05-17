"""OpenRouter cloud LLM provider."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import (
    ArticleSummary,
    SummarizerProvider,
    parse_summary_response,
)
from condenseit.providers.budget import BudgetTracker

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = (
    "You are a concise news analyst. Respond ONLY with a JSON object — "
    "no markdown, no code fences, no additional text. "
    "Write all JSON field values in English regardless of the article's language."
)


def _build_user_prompt(
    title: str,
    content: str,
    max_key_takeaways: int = 5,
    max_summary_paragraphs: int = 5,
) -> str:
    """Build the per-article user prompt with configurable output size."""
    takeaway_placeholders = ", ".join(
        f'"<takeaway {i + 1}>"' for i in range(max_key_takeaways)
    )
    para_word = "paragraph" if max_summary_paragraphs == 1 else "paragraphs"
    return (
        "Analyze this article and respond with a JSON object "
        "in exactly this structure. All values must be written in English:\n"
        f"{{\n"
        f'  "tldr": "<one sentence in English: what happened and why it matters>",\n'
        f'  "key_takeaways": [{takeaway_placeholders}],\n'
        f'  "summary": "<detailed summary in English, {max_summary_paragraphs} {para_word}>"\n'
        f"}}\n\n"
        f"Title: {title}\n"
        f"Content: {content}"
    )


class OpenRouterSummarizer(SummarizerProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        budget: BudgetTracker | None = None,
        max_key_takeaways: int = 5,
        max_summary_paragraphs: int = 5,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.budget = budget
        self.max_key_takeaways = max_key_takeaways
        self.max_summary_paragraphs = max_summary_paragraphs

    @property
    def model_name(self) -> str:
        return self.model

    def _chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 512,
    ) -> str:
        if self.budget and not self.budget.can_spend():
            raise RuntimeError("OpenRouter daily or monthly budget exceeded")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/condenseit/condenseit",
            "X-Title": "CondenseIt",
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        usage = data.get("usage", {})
        cost = float(data.get("usage", {}).get("cost", 0) or 0)
        if self.budget and cost > 0:
            self.budget.record_spend(
                cost,
                model=self.model,
                tokens=int(usage.get("total_tokens", 0)),
            )

        choices = data.get("choices", [])
        if not choices:
            return ""
        return str(choices[0]["message"]["content"]).strip()

    def summarize_article(self, article: dict[str, Any]) -> ArticleSummary:
        content = (article.get("content") or "")[:4000]
        title = article.get("title", "Untitled")
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(
                    title,
                    content,
                    self.max_key_takeaways,
                    self.max_summary_paragraphs,
                ),
            },
        ]
        raw = self._chat(messages, max_tokens=700)
        return parse_summary_response(raw)

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
