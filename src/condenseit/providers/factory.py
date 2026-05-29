"""Build summarizer from config and secrets."""

from __future__ import annotations

from condenseit.config import AppConfig
from condenseit.providers.base import SummarizerProvider
from condenseit.providers.budget import BudgetTracker
from condenseit.providers.fallback_chain import FallbackChainProvider
from condenseit.providers.ollama_provider import OllamaSummarizer
from condenseit.providers.openai_provider import OpenAISummarizer
from condenseit.providers.openrouter_models import pick_cheapest_text_model
from condenseit.providers.openrouter_provider import OpenRouterSummarizer
from condenseit.store.database import ContentStore
from condenseit.store.secure_keys import SecureKeyStore


def build_summarizer(
    config: AppConfig,
    store: ContentStore,
    digest_run_id: str = "",
) -> SummarizerProvider:
    keys = SecureKeyStore(store)
    provider = config.llm.provider.lower()
    model = config.model
    max_takeaways = config.max_key_takeaways
    max_paragraphs = config.max_summary_paragraphs

    if provider == "ollama":
        return OllamaSummarizer(
            model=model,
            host=config.llm.ollama_host,
            max_key_takeaways=max_takeaways,
            max_summary_paragraphs=max_paragraphs,
            digest_language=config.digest_language,
        )

    if provider == "openai":
        api_key = keys.get_key("openai") or config.llm.openai_api_key
        if not config.llm.openai_base_url:
            raise ValueError(
                "OpenAI-compatible base URL required "
                "(llm.openai_base_url or OPENAI_API_BASE_URL)"
            )
        return OpenAISummarizer(
            model=config.llm.openai_model or model,
            base_url=config.llm.openai_base_url,
            api_key=api_key,
            max_key_takeaways=max_takeaways,
            max_summary_paragraphs=max_paragraphs,
            digest_language=config.digest_language,
        )

    or_key = keys.get_key("openrouter") or config.llm.openrouter_api_key
    if not or_key:
        raise ValueError("OpenRouter API key required (admin or OPENROUTER_API_KEY)")

    budget = BudgetTracker(
        store,
        config.llm.openrouter_daily_budget_usd,
        config.llm.openrouter_monthly_budget_usd,
        digest_run_id=digest_run_id,
    )
    or_model = config.llm.openrouter_model or model
    if config.llm.openrouter_pick_cheapest:
        picked = pick_cheapest_text_model()
        if picked:
            or_model = picked

    cloud = OpenRouterSummarizer(
        or_model,
        or_key,
        budget=budget,
        max_key_takeaways=max_takeaways,
        max_summary_paragraphs=max_paragraphs,
        digest_language=config.digest_language,
    )

    if provider == "openrouter":
        return cloud

    if provider == "fallback":
        ollama = OllamaSummarizer(
            model=model,
            host=config.llm.ollama_host,
            max_key_takeaways=max_takeaways,
            max_summary_paragraphs=max_paragraphs,
            digest_language=config.digest_language,
        )
        return FallbackChainProvider(ollama, cloud)

    raise ValueError(f"Unknown llm.provider: {provider}")
