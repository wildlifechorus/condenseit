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
    openai_base_url = store.get_setting("openai_base_url", "")
    if openai_base_url:
        config.llm.openai_base_url = openai_base_url
    openai_model = store.get_setting("openai_model", "")
    if openai_model:
        config.llm.openai_model = openai_model
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
        except (json.JSONDecodeError, TypeError):
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
        except (json.JSONDecodeError, TypeError):
            pass

    # Keyword exclusions
    kw_raw = store.get_setting("exclude_keywords", "")
    if kw_raw:
        try:
            kw_list = json.loads(kw_raw)
            if isinstance(kw_list, list):
                config.exclude_keywords = [str(k) for k in kw_list]
        except (json.JSONDecodeError, TypeError):
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

    # Ranking / preference engine weights
    for key, attr, lo, hi in [
        ("tfidf_preference_weight", "tfidf_preference_weight", 0.0, 5.0),
        ("category_preference_weight", "category_preference_weight", 0.0, 5.0),
        ("source_preference_weight", "source_preference_weight", 0.0, 5.0),
        ("implicit_signal_weight", "implicit_signal_weight", 0.0, 1.0),
        ("embedding_preference_weight", "embedding_preference_weight", 0.0, 5.0),
        ("topic_score_weight", "topic_score_weight", 0.0, 5.0),
        ("llm_rerank_blend", "llm_rerank_blend", 0.0, 1.0),
        ("semantic_dedup_threshold", "semantic_dedup_threshold", 0.5, 1.0),
    ]:
        raw = store.get_setting(key, "")
        if raw:
            try:
                val_f = float(raw)
                if lo <= val_f <= hi:
                    setattr(config.relevance, attr, val_f)
            except ValueError:
                pass

    for key, attr, lo, hi in [
        ("rating_decay_half_life_days", "rating_decay_half_life_days", 1, 3650),
        ("min_ratings_for_learning", "min_ratings_for_learning", 1, 1000),
        ("llm_rerank_top_k", "llm_rerank_top_k", 5, 100),
    ]:
        raw = store.get_setting(key, "")
        if raw:
            try:
                val_i = int(raw)
                if lo <= val_i <= hi:
                    setattr(config.relevance, attr, val_i)
            except ValueError:
                pass

    # Feature flag overrides stored as "1"/"0" strings.
    for key, attr in [
        ("llm_rerank_enabled", "llm_rerank_enabled"),
        ("semantic_dedup_enabled", "semantic_dedup_enabled"),
    ]:
        raw = store.get_setting(key, "")
        if raw == "1":
            setattr(config.relevance, attr, True)
        elif raw == "0":
            setattr(config.relevance, attr, False)

    for key, attr in [
        ("embedding_provider", "embedding_provider"),
        ("embedding_model", "embedding_model"),
        ("llm_rerank_model", "llm_rerank_model"),
    ]:
        raw = store.get_setting(key, "")
        if raw:
            setattr(config.relevance, attr, raw)

    # Phase 5: Apply cold-start bootstrap keywords when no YAML keywords are set.
    bootstrap_raw = store.get_setting("bootstrap_initial_keywords", "")
    if bootstrap_raw:
        try:
            bootstrap_kw = json.loads(bootstrap_raw)
            if isinstance(bootstrap_kw, dict):
                existing_high = config.relevance.initial_keywords.get("high", [])
                existing_medium = config.relevance.initial_keywords.get("medium", [])
                # Merge: YAML keywords take precedence; bootstrap fills gaps.
                merged_high = list(
                    {*existing_high, *bootstrap_kw.get("high", [])}
                )
                merged_medium = list(
                    {*existing_medium, *bootstrap_kw.get("medium", [])}
                )
                config.relevance.initial_keywords = {
                    "high": merged_high,
                    "medium": merged_medium,
                }
        except (json.JSONDecodeError, TypeError):
            pass

    bootstrap_synonyms_raw = store.get_setting("bootstrap_synonyms", "")
    if bootstrap_synonyms_raw:
        try:
            syn = json.loads(bootstrap_synonyms_raw)
            if isinstance(syn, dict):
                merged = dict(config.relevance.topic_synonyms)
                for k, v in syn.items():
                    if k not in merged:
                        merged[k] = v
                config.relevance.topic_synonyms = merged
        except (json.JSONDecodeError, TypeError):
            pass

    # YouTube transcription (audio-based via OpenRouter Whisper)
    yt_transcription_raw = store.get_setting("youtube_transcription_enabled", "")
    if yt_transcription_raw == "1":
        config.youtube_transcription.enabled = True
    elif yt_transcription_raw == "0":
        config.youtube_transcription.enabled = False

    yt_transcription_model = store.get_setting("youtube_transcription_model", "")
    if yt_transcription_model:
        config.youtube_transcription.model = yt_transcription_model

    yt_max_dur = store.get_setting("youtube_transcription_max_duration", "")
    if yt_max_dur:
        try:
            val = int(yt_max_dur)
            if 60 <= val <= 7200:
                config.youtube_transcription.max_duration_seconds = val
        except ValueError:
            pass

    return config
