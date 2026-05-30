"""OpenRouter cloud LLM provider."""

import logging
import time
from typing import Any

import httpx

from condenseit.api_urls import OPENROUTER_CHAT_URL
from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import (
    ArticleSummary,
    SummarizerProvider,
    build_chat_system_prompt,
    build_chat_user_prompt,
    parse_summary_response,
    resolve_digest_language,
)
from condenseit.providers.budget import BudgetTracker

logger = logging.getLogger(__name__)

_RETRY_WAITS = [5, 15, 30]


class OpenRouterSummarizer(SummarizerProvider):
    def __init__(
        self,
        model: str,
        api_key: str,
        budget: BudgetTracker | None = None,
        max_key_takeaways: int = 5,
        max_summary_paragraphs: int = 5,
        digest_language: str = "en",
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.budget = budget
        self.max_key_takeaways = max_key_takeaways
        self.max_summary_paragraphs = max_summary_paragraphs
        self.digest_language = digest_language

    @property
    def model_name(self) -> str:
        return self.model

    def _chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 1400,
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
        resp: httpx.Response | None = None
        with httpx.Client(timeout=120.0) as client:
            for attempt in range(len(_RETRY_WAITS) + 1):
                resp = client.post(
                    OPENROUTER_CHAT_URL,
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 429:
                    resp.raise_for_status()
                    break
                if attempt >= len(_RETRY_WAITS):
                    resp.raise_for_status()
                wait = int(resp.headers.get("Retry-After") or _RETRY_WAITS[attempt])
                logger.warning(
                    "OpenRouter 429 rate limit; retrying in %ds (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    len(_RETRY_WAITS),
                )
                time.sleep(wait)
        data = resp.json()  # type: ignore[union-attr]

        usage_raw = data.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        cost = float(usage.get("cost") or 0)
        if self.budget and cost > 0:
            self.budget.record_spend(
                cost,
                model=self.model,
                tokens=int(usage.get("total_tokens", 0)),
            )

        choices = data.get("choices", [])
        if not choices:
            return ""
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            logger.warning(
                "OpenRouter response truncated (finish_reason=length) for model=%s; "
                "consider raising max_tokens",
                self.model,
            )
        return str(choice["message"]["content"]).strip()

    def summarize_article(
        self,
        article: dict[str, Any],
    ) -> ArticleSummary:
        content = (article.get("content") or "")[:4000]
        title = article.get("title", "Untitled")
        language = resolve_digest_language(self.digest_language, content)
        messages = [
            {"role": "system", "content": build_chat_system_prompt(language)},
            {
                "role": "user",
                "content": build_chat_user_prompt(
                    title,
                    content,
                    self.max_key_takeaways,
                    self.max_summary_paragraphs,
                    language=language,
                ),
            },
        ]
        raw = self._chat(messages, max_tokens=1400)
        return parse_summary_response(raw)

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
