"""Ollama-backed summarization."""

from __future__ import annotations

from typing import Any

import ollama

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import ArticleSummary, SummarizerProvider, parse_summary_response

# Prompt that asks for a strict JSON response.  Tested against llama3, mistral,
# phi3, and gemma2; most 7B+ models follow it reliably.
_SUMMARY_PROMPT = """\
Analyze this article and respond ONLY with a JSON object — no markdown, no \
code fences, no extra text.

Use exactly this structure:
{{
  "tldr": "<one sentence: what happened and why it matters>",
  "key_takeaways": ["<takeaway 1>", "<takeaway 2>", "<takeaway 3>"],
  "summary": "<detailed summary in 3 paragraphs: first paragraph covers what happened and the key events; second paragraph covers the implications and why it matters; third paragraph covers context, background, or conclusions>"
}}

Title: {title}
Content: {content}

JSON:"""


class OllamaSummarizer(SummarizerProvider):
    def __init__(self, model: str, host: str = "http://localhost:11434") -> None:
        self.model = model
        self.client = ollama.Client(host=host)

    @property
    def model_name(self) -> str:
        return self.model

    def summarize_article(self, article: dict[str, Any]) -> ArticleSummary:
        content = (article.get("content") or "")[:4000]
        title = article.get("title", "Untitled")
        prompt = _SUMMARY_PROMPT.format(title=title, content=content)
        # One request per digest item; wall time scales with max_articles_per_digest.
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": 0.3, "num_predict": 700},
        )
        return parse_summary_response(response["response"])

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
