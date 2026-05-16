"""Try local Ollama first, then OpenRouter."""

from __future__ import annotations

import logging
from typing import Any

from condenseit.providers.base import ArticleSummary, SummarizerProvider

logger = logging.getLogger(__name__)


class FallbackChainProvider(SummarizerProvider):
    def __init__(
        self,
        primary: SummarizerProvider,
        fallback: SummarizerProvider,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self._active = primary

    @property
    def model_name(self) -> str:
        return self._active.model_name

    def summarize_article(self, article: dict[str, Any]) -> ArticleSummary:
        for provider in (self.primary, self.fallback):
            try:
                result = provider.summarize_article(article)
                self._active = provider
                return result
            except Exception:
                logger.exception(
                    "Provider %s failed for summarize_article",
                    provider.model_name,
                )
        raise RuntimeError("All LLM providers failed")

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        for provider in (self.primary, self.fallback):
            try:
                result = provider.generate_digest(categorized, changes, videos)
                self._active = provider
                return result
            except Exception:
                logger.exception(
                    "Provider %s failed for generate_digest",
                    provider.model_name,
                )
        raise RuntimeError("All LLM providers failed")
