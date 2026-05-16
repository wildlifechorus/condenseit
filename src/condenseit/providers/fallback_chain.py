"""Try local Ollama first, then OpenRouter."""

from __future__ import annotations

import logging
from typing import Any

from condenseit.providers.base import SummarizerProvider

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

    def _call(self, method: str, *args: Any, **kwargs: Any) -> str:
        for provider in (self.primary, self.fallback):
            try:
                fn = getattr(provider, method)
                result: str = fn(*args, **kwargs)
                self._active = provider
                return result
            except Exception:
                logger.exception(
                    "Provider %s failed for %s",
                    provider.model_name,
                    method,
                )
        raise RuntimeError("All LLM providers failed")

    def summarize_article(self, article: dict[str, Any]) -> str:
        return self._call("summarize_article", article)

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return self._call("generate_digest", categorized, changes, videos)
