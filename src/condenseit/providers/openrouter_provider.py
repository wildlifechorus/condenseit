"""OpenRouter cloud LLM provider."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import SummarizerProvider
from condenseit.providers.budget import BudgetTracker

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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

    def _chat(self, prompt: str, max_tokens: int = 512) -> str:
        if self.budget and not self.budget.can_spend():
            raise RuntimeError("OpenRouter daily or monthly budget exceeded")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
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

    def summarize_article(self, article: dict[str, Any]) -> str:
        content = (article.get("content") or "")[:4000]
        title = article.get("title", "Untitled")
        prompt = (
            f"Summarize in 2-3 sentences.\nTitle: {title}\nContent: {content}\nSummary:"
        )
        return self._chat(prompt, max_tokens=200)

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
