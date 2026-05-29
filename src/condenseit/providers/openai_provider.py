"""OpenAI-compatible endpoint provider (v1/chat/completions)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import (
    ArticleSummary,
    SummarizerProvider,
    build_chat_system_prompt,
    build_chat_user_prompt,
    parse_summary_response,
    resolve_digest_language,
)

logger = logging.getLogger(__name__)

_RETRY_WAITS = [5, 15, 30]


class OpenAISummarizer(SummarizerProvider):
    """Summarizer that calls any OpenAI-compatible /v1/chat/completions endpoint.

    Works with Ollama's OpenAI compat layer, LM Studio, vLLM, llama.cpp,
    text-generation-inference, and real OpenAI / Azure OpenAI endpoints.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str = "",
        max_key_takeaways: int = 5,
        max_summary_paragraphs: int = 5,
        digest_language: str = "en",
    ) -> None:
        self.model = model
        # Normalise: strip trailing slash so we can always append /chat/completions.
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
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
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        resp: httpx.Response | None = None
        with httpx.Client(timeout=120.0) as client:
            for attempt in range(len(_RETRY_WAITS) + 1):
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code != 429:
                    resp.raise_for_status()
                    break
                if attempt >= len(_RETRY_WAITS):
                    resp.raise_for_status()
                wait = int(resp.headers.get("Retry-After") or _RETRY_WAITS[attempt])
                logger.warning(
                    "OpenAI-compat 429 rate limit; retrying in %ds (attempt %d/%d)",
                    wait,
                    attempt + 1,
                    len(_RETRY_WAITS),
                )
                time.sleep(wait)

        data = resp.json()  # type: ignore[union-attr]
        choices = data.get("choices", [])
        if not choices:
            return ""
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            logger.warning(
                "OpenAI-compat response truncated (finish_reason=length) for model=%s; "
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
        raw = self._chat(messages)
        return parse_summary_response(raw)

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
