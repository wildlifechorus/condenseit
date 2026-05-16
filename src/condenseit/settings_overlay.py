"""Apply admin DB settings onto AppConfig."""

from __future__ import annotations

import json

from condenseit.config import AppConfig
from condenseit.store.database import ContentStore


def apply_db_settings(config: AppConfig, store: ContentStore) -> AppConfig:
    # LLM settings
    model = store.get_setting("model")
    if model:
        config.model = model
    provider = store.get_setting("llm_provider")
    if provider:
        config.llm.provider = provider
    or_model = store.get_setting("openrouter_model")
    if or_model:
        config.llm.openrouter_model = or_model
    pick = store.get_setting("openrouter_pick_cheapest", "")
    if pick == "1":
        config.llm.openrouter_pick_cheapest = True
    elif pick == "0":
        config.llm.openrouter_pick_cheapest = False

    # Schedule settings
    schedule_raw = store.get_setting("schedule_times", "")
    if schedule_raw:
        try:
            times = json.loads(schedule_raw)
            if isinstance(times, list):
                config.schedule["times"] = [str(t) for t in times]
        except Exception:
            pass

    # Digest pipeline settings
    max_articles = store.get_setting("max_articles_per_digest", "")
    if max_articles:
        try:
            val = int(max_articles)
            if 1 <= val <= 200:
                config.max_articles_per_digest = val
        except ValueError:
            pass

    balance = store.get_setting("balance_digest_categories", "")
    if balance == "1":
        config.balance_digest_categories = True
    elif balance == "0":
        config.balance_digest_categories = False

    max_per_cat = store.get_setting("max_articles_per_category", "")
    if max_per_cat:
        try:
            val = int(max_per_cat)
            if 1 <= val <= 50:
                config.max_articles_per_category = val
        except ValueError:
            pass

    max_age = store.get_setting("max_article_age_hours", "")
    if max_age:
        try:
            val = int(max_age)
            if val >= 0:
                config.max_article_age_hours = val
        except ValueError:
            pass

    # Language preferences
    langs_raw = store.get_setting("preferred_languages", "")
    if langs_raw:
        try:
            langs = json.loads(langs_raw)
            if isinstance(langs, list):
                config.preferred_languages = [str(language) for language in langs]
        except Exception:
            pass

    # Keyword exclusions
    kw_raw = store.get_setting("exclude_keywords", "")
    if kw_raw:
        try:
            kw_list = json.loads(kw_raw)
            if isinstance(kw_list, list):
                config.exclude_keywords = [str(k) for k in kw_list]
        except Exception:
            pass

    # OpenRouter budget limits
    daily_budget = store.get_setting("openrouter_daily_budget_usd", "")
    if daily_budget:
        try:
            val = float(daily_budget)
            if val >= 0:
                config.llm.openrouter_daily_budget_usd = val
        except ValueError:
            pass

    monthly_budget = store.get_setting("openrouter_monthly_budget_usd", "")
    if monthly_budget:
        try:
            val = float(monthly_budget)
            if val >= 0:
                config.llm.openrouter_monthly_budget_usd = val
        except ValueError:
            pass

    # LLM summarization tuning
    max_takeaways = store.get_setting("max_key_takeaways", "")
    if max_takeaways:
        try:
            val = int(max_takeaways)
            if 1 <= val <= 10:
                config.max_key_takeaways = val
        except ValueError:
            pass

    max_paragraphs = store.get_setting("max_summary_paragraphs", "")
    if max_paragraphs:
        try:
            val = int(max_paragraphs)
            if 1 <= val <= 10:
                config.max_summary_paragraphs = val
        except ValueError:
            pass

    return config
