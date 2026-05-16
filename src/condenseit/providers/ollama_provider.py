"""Ollama-backed summarization."""

from __future__ import annotations

from typing import Any

import ollama

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import SummarizerProvider


class OllamaSummarizer(SummarizerProvider):
    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        self.model = model
        self.client = ollama.Client(host=host)

    @property
    def model_name(self) -> str:
        return self.model

    def summarize_article(self, article: dict[str, Any]) -> str:
        content = (article.get("content") or "")[:4000]
        title = article.get("title", "Untitled")
        prompt = f"""Summarize this article in 2-3 sentences. Focus on:
- What happened or what is new
- Why it matters

Title: {title}
Content: {content}

Summary:"""
        # One request per digest item; wall time scales with max_articles_per_digest.
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": 0.3, "num_predict": 200},
        )
        return response["response"].strip()

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
