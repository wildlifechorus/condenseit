"""Apply admin DB settings onto AppConfig."""

from condenseit.config import AppConfig
from condenseit.setting_parsers import (
    parse_float_in_range,
    parse_float_min,
    parse_int_in_range,
    parse_int_min,
    parse_json_dict,
    parse_json_list,
)
from condenseit.store.database import ContentStore


def _apply_llm_settings(config: AppConfig, store: ContentStore) -> None:
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

    daily_budget = store.get_setting("openrouter_daily_budget_usd", "")
    if daily_budget:
        val = parse_float_min(daily_budget, "openrouter_daily_budget_usd", 0.0)
        if val is not None:
            config.llm.openrouter_daily_budget_usd = val

    monthly_budget = store.get_setting("openrouter_monthly_budget_usd", "")
    if monthly_budget:
        val = parse_float_min(monthly_budget, "openrouter_monthly_budget_usd", 0.0)
        if val is not None:
            config.llm.openrouter_monthly_budget_usd = val


def _apply_schedule_settings(config: AppConfig, store: ContentStore) -> None:
    schedule_raw = store.get_setting("schedule_times", "")
    times = parse_json_list(schedule_raw, "schedule_times")
    if times is not None:
        config.schedule["times"] = times


def _apply_digest_settings(config: AppConfig, store: ContentStore) -> None:
    max_articles = store.get_setting("max_articles_per_digest", "")
    if max_articles:
        val = parse_int_in_range(max_articles, "max_articles_per_digest", 1, 200)
        if val is not None:
            config.max_articles_per_digest = val

    balance = store.get_setting("balance_digest_categories", "")
    if balance == "1":
        config.balance_digest_categories = True
    elif balance == "0":
        config.balance_digest_categories = False

    max_per_cat = store.get_setting("max_articles_per_category", "")
    if max_per_cat:
        val = parse_int_in_range(max_per_cat, "max_articles_per_category", 1, 50)
        if val is not None:
            config.max_articles_per_category = val

    max_age = store.get_setting("max_article_age_hours", "")
    if max_age:
        val = parse_int_min(max_age, "max_article_age_hours", 0)
        if val is not None:
            config.max_article_age_hours = val

    digest_lang = store.get_setting("digest_language", "")
    if digest_lang:
        config.digest_language = digest_lang

    langs_raw = store.get_setting("preferred_languages", "")
    langs = parse_json_list(langs_raw, "preferred_languages")
    if langs is not None:
        config.preferred_languages = langs

    kw_raw = store.get_setting("exclude_keywords", "")
    kw_list = parse_json_list(kw_raw, "exclude_keywords")
    if kw_list is not None:
        config.exclude_keywords = kw_list

    max_takeaways = store.get_setting("max_key_takeaways", "")
    if max_takeaways:
        val = parse_int_in_range(max_takeaways, "max_key_takeaways", 1, 10)
        if val is not None:
            config.max_key_takeaways = val

    max_paragraphs = store.get_setting("max_summary_paragraphs", "")
    if max_paragraphs:
        val = parse_int_in_range(max_paragraphs, "max_summary_paragraphs", 1, 10)
        if val is not None:
            config.max_summary_paragraphs = val


def _apply_relevance_settings(config: AppConfig, store: ContentStore) -> None:
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
            val_f = parse_float_in_range(raw, key, lo, hi)
            if val_f is not None:
                setattr(config.relevance, attr, val_f)

    for key, attr, lo, hi in [
        ("rating_decay_half_life_days", "rating_decay_half_life_days", 1, 3650),
        ("min_ratings_for_learning", "min_ratings_for_learning", 1, 1000),
        ("llm_rerank_top_k", "llm_rerank_top_k", 5, 100),
    ]:
        raw = store.get_setting(key, "")
        if raw:
            val_i = parse_int_in_range(raw, key, lo, hi)
            if val_i is not None:
                setattr(config.relevance, attr, val_i)

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

    bootstrap_raw = store.get_setting("bootstrap_initial_keywords", "")
    bootstrap_kw = parse_json_dict(bootstrap_raw, "bootstrap_initial_keywords")
    if bootstrap_kw is not None:
        existing_high = config.relevance.initial_keywords.get("high", [])
        existing_medium = config.relevance.initial_keywords.get("medium", [])
        merged_high = list({*existing_high, *bootstrap_kw.get("high", [])})
        merged_medium = list({*existing_medium, *bootstrap_kw.get("medium", [])})
        config.relevance.initial_keywords = {
            "high": merged_high,
            "medium": merged_medium,
        }

    bootstrap_synonyms_raw = store.get_setting("bootstrap_synonyms", "")
    syn = parse_json_dict(bootstrap_synonyms_raw, "bootstrap_synonyms")
    if syn is not None:
        merged = dict(config.relevance.topic_synonyms)
        for k, v in syn.items():
            if k not in merged:
                merged[k] = v
        config.relevance.topic_synonyms = merged


def _apply_youtube_settings(config: AppConfig, store: ContentStore) -> None:
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
        val = parse_int_in_range(
            yt_max_dur, "youtube_transcription_max_duration", 60, 7200
        )
        if val is not None:
            config.youtube_transcription.max_duration_seconds = val


def apply_db_settings(config: AppConfig, store: ContentStore) -> AppConfig:
    _apply_llm_settings(config, store)
    _apply_schedule_settings(config, store)
    _apply_digest_settings(config, store)
    _apply_relevance_settings(config, store)
    _apply_youtube_settings(config, store)
    return config
