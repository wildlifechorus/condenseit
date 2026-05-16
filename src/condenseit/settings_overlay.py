"""Apply admin DB settings onto AppConfig."""

from __future__ import annotations

from condenseit.config import AppConfig
from condenseit.store.database import ContentStore


def apply_db_settings(config: AppConfig, store: ContentStore) -> AppConfig:
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
    return config
