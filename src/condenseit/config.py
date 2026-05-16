"""Load and validate configuration from YAML and environment."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class FeedConfig(BaseModel):
    url: str
    category: str = "General"
    priority: int = 2


class YouTubeChannelConfig(BaseModel):
    handle: str = ""
    channel_id: str
    category: str = "Video"


class WatchUrlConfig(BaseModel):
    url: str
    category: str = "General"
    selector: str | None = None
    change_threshold: float = 0.05


class RelevanceConfig(BaseModel):
    initial_keywords: dict[str, list[str]] = Field(
        default_factory=lambda: {"high": [], "medium": []},
    )
    min_ratings_for_learning: int = 5
    tfidf_preference_weight: float = 0.35
    category_preference_weight: float = 0.6
    source_preference_weight: float = 0.3
    rating_decay_half_life_days: int = 30


class OutputConfig(BaseModel):
    format: str = "both"
    path: str = "data/digests"


class LlmConfig(BaseModel):
    provider: str = "openrouter"
    ollama_host: str = "http://localhost:11434"
    manage_lifecycle: bool = True
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_daily_budget_usd: float = 1.0
    openrouter_monthly_budget_usd: float = 10.0
    openrouter_pick_cheapest: bool = True


class VpsConfig(BaseModel):
    """When enabled, rsync runs if vps.host is set."""

    enabled: bool = True
    host: str = ""
    path: str = "/var/www/condenseit/"
    ssh_key: str = "~/.ssh/id_ed25519"
    ssh_port: int = 22
    digest_url: str = ""


class AppConfig(BaseModel):
    model: str = "llama3.2:3b"
    max_articles_per_digest: int = Field(default=50, ge=1, le=200)
    balance_digest_categories: bool = True
    max_articles_per_category: int = Field(default=5, ge=1, le=50)
    max_article_age_hours: int = Field(default=36, ge=0)
    # ISO 639-1 language codes; empty list means accept all languages.
    preferred_languages: list[str] = Field(default_factory=list)
    # LLM summarization tuning.
    max_key_takeaways: int = Field(default=5, ge=1, le=10)
    max_summary_paragraphs: int = Field(default=5, ge=1, le=10)
    schedule: dict[str, list[str]] = Field(
        default_factory=lambda: {"times": ["07:00", "18:00"]},
    )
    feeds: list[FeedConfig] = Field(default_factory=list)
    youtube_channels: list[YouTubeChannelConfig] = Field(default_factory=list)
    watch_urls: list[WatchUrlConfig] = Field(default_factory=list)
    relevance: RelevanceConfig = Field(default_factory=RelevanceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    vps: VpsConfig = Field(default_factory=VpsConfig)


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env(value: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        return ""

    return _ENV_PATTERN.sub(replacer, value)


def _expand_dict(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _expand_dict(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_dict(item) for item in data]
    if isinstance(data, str):
        return _expand_env(data)
    return data


def get_data_dir() -> Path:
    raw = os.environ.get("CONDENSEIT_DATA_DIR", "data")
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_config_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env_path = os.environ.get("CONDENSEIT_CONFIG")
    if env_path:
        return Path(env_path).expanduser()
    return Path("config.yaml")


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = get_config_path(str(path) if path else None)
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        for env_file in (config_path.parent / ".env", Path.cwd() / ".env"):
            if env_file.is_file():
                load_dotenv(env_file, override=False)
                break

    if not config_path.exists():
        example = Path("config.example.yaml")
        if example.exists():
            raw = yaml.safe_load(example.read_text(encoding="utf-8"))
        else:
            raw = {}
    else:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    expanded = _expand_dict(raw)
    # Remove stale/removed sections from YAML so they don't cause validation errors.
    expanded.pop("email", None)
    expanded.pop("sync", None)

    if os.environ.get("OLLAMA_HOST"):
        llm = expanded.setdefault("llm", {})
        llm["ollama_host"] = os.environ["OLLAMA_HOST"]
        llm["manage_lifecycle"] = False

    if os.environ.get("OPENROUTER_API_KEY"):
        expanded.setdefault("llm", {})["openrouter_api_key"] = os.environ[
            "OPENROUTER_API_KEY"
        ]

    cap = os.environ.get("CONDENSEIT_MAX_ARTICLES_PER_DIGEST", "").strip()
    if cap:
        try:
            expanded["max_articles_per_digest"] = int(cap)
        except ValueError:
            pass

    vps_host = os.environ.get("DIGEST_PWA_SSH_HOST", "").strip()
    if vps_host:
        expanded.setdefault("vps", {})["host"] = vps_host
    vps_path = os.environ.get("DIGEST_PWA_REMOTE_DIR", "").strip()
    if vps_path:
        expanded.setdefault("vps", {})["path"] = vps_path
    vps_digest_url = os.environ.get("DIGEST_PWA_LIVE_URL", "").strip()
    if vps_digest_url:
        expanded.setdefault("vps", {})["digest_url"] = vps_digest_url

    return AppConfig.model_validate(expanded)


def resolve_output_path(config: AppConfig) -> Path:
    raw = config.output.path
    if raw.startswith("data/") or raw == "data/digests":
        path = get_data_dir() / "digests"
    else:
        path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path
