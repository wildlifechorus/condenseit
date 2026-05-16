"""LLM provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SummarizerProvider(ABC):
    @abstractmethod
    def summarize_article(self, article: dict[str, Any]) -> str:
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
