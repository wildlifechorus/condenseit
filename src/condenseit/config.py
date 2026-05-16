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
    provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    manage_lifecycle: bool = True
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_daily_budget_usd: float = 1.0
    openrouter_monthly_budget_usd: float = 10.0
    openrouter_pick_cheapest: bool = False


class EmailConfig(BaseModel):
    """When enabled, digest email runs if a Resend key is configured."""

    enabled: bool = True
    resend_api_key: str = ""
    from_address: str = Field(default="CondenseIt <digest@example.com>", alias="from")
    to: str = "you@example.com"

    model_config = {"populate_by_name": True}


class VpsConfig(BaseModel):
    """When enabled, rsync runs if vps.host is set."""

    enabled: bool = True
    host: str = ""
    path: str = "/var/www/condenseit/"
    ssh_key: str = "~/.ssh/id_ed25519"
    ssh_port: int = 22
    digest_url: str = ""


class DigestPwaConfig(BaseModel):
    """Static installable digest (output of ``condenseit pwa-build``)."""

    output_dir: str = "data/pwa-dist"
    # Baked into the PWA at build time: optional GET URL to merge read-only
    # ratings JSON (same schema as export) into localStorage on load.
    ratings_merge_url: str = ""
    # Host-side: import ratings before each ``condenseit run`` (no secrets here;
    # use CONDENSEIT_RATINGS_IMPORT_BEARER_TOKEN for authenticated URL fetch).
    ratings_import_path: str = ""
    ratings_import_url: str = ""
    # Host-side: import read URLs from a remote /api/read/export endpoint before
    # each ``condenseit run`` so the pipeline excludes remotely-read articles.
    # Use CONDENSEIT_READ_IMPORT_URL env var or set this field.
    # Bearer token from CONDENSEIT_READ_IMPORT_BEARER_TOKEN if auth is needed.
    read_import_url: str = ""


class AppConfig(BaseModel):
    model: str = "llama3.2:3b"
    # More items mean more sequential LLM calls; cap keeps config mistakes bounded.
    max_articles_per_digest: int = Field(default=50, ge=1, le=200)
    balance_digest_categories: bool = True
    max_articles_per_category: int = Field(default=5, ge=1, le=50)
    # Articles whose published_at is older than this many hours are dropped before
    # ranking. Set to 0 to disable the age gate entirely.
    max_article_age_hours: int = Field(default=36, ge=0)
    schedule: dict[str, list[str]] = Field(
        default_factory=lambda: {"times": ["07:00", "18:00"]},
    )
    feeds: list[FeedConfig] = Field(default_factory=list)
    youtube_channels: list[YouTubeChannelConfig] = Field(default_factory=list)
    watch_urls: list[WatchUrlConfig] = Field(default_factory=list)
    relevance: RelevanceConfig = Field(default_factory=RelevanceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    vps: VpsConfig = Field(default_factory=VpsConfig)
    digest_pwa: DigestPwaConfig = Field(default_factory=DigestPwaConfig)


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
    if os.environ.get("OLLAMA_HOST"):
        llm = expanded.setdefault("llm", {})
        llm["ollama_host"] = os.environ["OLLAMA_HOST"]
        llm["manage_lifecycle"] = False

    if os.environ.get("OPENROUTER_API_KEY"):
        expanded.setdefault("llm", {})["openrouter_api_key"] = os.environ[
            "OPENROUTER_API_KEY"
        ]

    if os.environ.get("RESEND_API_KEY"):
        email_cfg = expanded.setdefault("email", {})
        email_cfg["resend_api_key"] = os.environ["RESEND_API_KEY"]

    resend_from = os.environ.get("RESEND_FROM", "").strip()
    if resend_from:
        expanded.setdefault("email", {})["from"] = resend_from

    digest_email_to = os.environ.get("DIGEST_EMAIL_TO", "").strip()
    if digest_email_to:
        expanded.setdefault("email", {})["to"] = digest_email_to

    cap = os.environ.get("CONDENSEIT_MAX_ARTICLES_PER_DIGEST", "").strip()
    if cap:
        try:
            expanded["max_articles_per_digest"] = int(cap)
        except ValueError:
            pass

    # Same names as scripts/deploy-digest-pwa.sh (rsync after ``condenseit run``).
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
