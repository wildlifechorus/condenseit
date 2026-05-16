"""Build summarizer from config and secrets."""

from __future__ import annotations

from condenseit.config import AppConfig
from condenseit.providers.base import SummarizerProvider
from condenseit.providers.budget import BudgetTracker
from condenseit.providers.fallback_chain import FallbackChainProvider
from condenseit.providers.ollama_provider import OllamaSummarizer
from condenseit.providers.openrouter_models import pick_cheapest_text_model
from condenseit.providers.openrouter_provider import OpenRouterSummarizer
from condenseit.store.database import ContentStore
from condenseit.store.secure_keys import SecureKeyStore


def build_summarizer(config: AppConfig, store: ContentStore) -> SummarizerProvider:
    keys = SecureKeyStore(store)
    provider = config.llm.provider.lower()
    model = config.model

    ollama = OllamaSummarizer(model=model, host=config.llm.ollama_host)

    if provider == "ollama":
        return ollama

    or_key = keys.get_key("openrouter") or config.llm.openrouter_api_key
    if not or_key:
        raise ValueError("OpenRouter API key required (admin or OPENROUTER_API_KEY)")

    budget = BudgetTracker(
        store,
        config.llm.openrouter_daily_budget_usd,
        config.llm.openrouter_monthly_budget_usd,
    )
    or_model = config.llm.openrouter_model or model
    if config.llm.openrouter_pick_cheapest:
        picked = pick_cheapest_text_model()
        if picked:
            or_model = picked

    cloud = OpenRouterSummarizer(or_model, or_key, budget=budget)

    if provider == "openrouter":
        return cloud

    if provider == "fallback":
        return FallbackChainProvider(ollama, cloud)

    raise ValueError(f"Unknown llm.provider: {provider}")
