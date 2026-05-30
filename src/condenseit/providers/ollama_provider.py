"""Ollama-backed summarization."""

import logging
from typing import Any

import ollama

from condenseit.digest.format import build_digest_markdown
from condenseit.providers.base import (
    ArticleSummary,
    SummarizerProvider,
    parse_summary_response,
    resolve_digest_language,
)

logger = logging.getLogger(__name__)


def _build_summary_prompt(
    title: str,
    content: str,
    max_key_takeaways: int = 5,
    max_summary_paragraphs: int = 5,
    language: str = "English",
) -> str:
    """Build the per-article summarization prompt with configurable output size.

    ``language`` is a human-readable language name such as ``"English"`` or
    ``"French"``.
    """
    takeaway_placeholders = ", ".join(
        f'"<takeaway {i + 1}>"' for i in range(max_key_takeaways)
    )
    para_word = "paragraph" if max_summary_paragraphs == 1 else "paragraphs"

    return (
        "Analyze this article and respond ONLY with a JSON object — no markdown, "
        f"no code fences, no extra text. All values must be written in {language}.\n\n"
        "Use exactly this structure:\n"
        f"{{\n"
        f'  "tldr": "<one sentence in {language}: what happened and why it matters>",\n'
        f'  "key_takeaways": [{takeaway_placeholders}],\n'
        f'  "summary": "<detailed summary in {language}, {max_summary_paragraphs} {para_word}>",\n'  # noqa: E501
        f'  "topics": ["<topic-1>", "<topic-2>", "<topic-3>"],\n'
        f'  "entities": ["<person-org-product-1>", "<entity-2>"],\n'
        f'  "novelty": <integer 1-5: how surprising or novel vs mainstream coverage>\n'
        f"}}\n\n"
        f"Title: {title}\n"
        f"Content: {content}\n\n"
        "JSON:"
    )


class OllamaSummarizer(SummarizerProvider):
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        max_key_takeaways: int = 5,
        max_summary_paragraphs: int = 5,
        digest_language: str = "en",
    ) -> None:
        self.model = model
        self.client = ollama.Client(host=host)
        self.max_key_takeaways = max_key_takeaways
        self.max_summary_paragraphs = max_summary_paragraphs
        self.digest_language = digest_language

    @property
    def model_name(self) -> str:
        return self.model

    def summarize_article(
        self,
        article: dict[str, Any],
    ) -> ArticleSummary:
        content = (article.get("content") or "")[:4000]
        title = article.get("title", "Untitled")
        language = resolve_digest_language(self.digest_language, content)
        prompt = _build_summary_prompt(
            title,
            content,
            self.max_key_takeaways,
            self.max_summary_paragraphs,
            language=language,
        )
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            think=False,
            options={"temperature": 0.3, "num_predict": 1400},
        )
        if response.get("done_reason") == "length":
            logger.warning(
                "Ollama response truncated (done_reason=length) for model=%s; "
                "consider raising num_predict",
                self.model,
            )
        return parse_summary_response(response["response"])

    def generate_digest(
        self,
        categorized: dict[str, list[dict[str, Any]]],
        changes: list[dict[str, str]] | None = None,
        videos: list[dict[str, Any]] | None = None,
    ) -> str:
        return build_digest_markdown(categorized, changes, videos)
