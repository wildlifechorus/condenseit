"""OpenRouter cloud LLM provider."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import ArticleSummary, SummarizerProvider, parse_summary_response
from condenseit.providers.budget import BudgetTracker

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SYSTEM_PROMPT = (
    "You are a concise news analyst. Respond ONLY with a JSON object — "
    "no markdown, no code fences, no additional text."
)

_USER_PROMPT = """\
Analyze this article and respond with a JSON object in exactly this structure:
{{
  "tldr": "<one sentence: what happened and why it matters>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "summary": "<detailed summary in 3 paragraphs: first paragraph covers what happened and the key events; second paragraph covers the implications and why it matters; third paragraph covers context, background, or conclusions>"
}}

Title: {title}
Content: {content}"""


class OpenRouterSummarizer(SummarizerProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        budget: BudgetTracker | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.budget = budget

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
                "content": _USER_PROMPT.format(title=title, content=content),
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
