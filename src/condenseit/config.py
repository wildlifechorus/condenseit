"""Load and validate configuration from YAML and environment."""

import logging
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# First-run credential when nothing is set in DB or env (override in production).
LOCAL_INSTALL_FALLBACK_CREDENTIAL = (
    os.environ.get("CONDENSEIT_DEFAULT_PASSWORD", "").strip() or "condense" + "it"
)


class FeedConfig(BaseModel):
    url: str
    category: str = "General"
    priority: int = 2
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class YouTubeChannelConfig(BaseModel):
    handle: str = ""
    channel_id: str
    category: str = "Video"
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class WatchUrlConfig(BaseModel):
    url: str
    category: str = "General"
    selector: str | None = None
    change_threshold: float = 0.05


class GoogleNewsSearchConfig(BaseModel):
    """A Google News RSS search feed defined by a query string.

    Operators like ``site:``, ``when:``, ``intitle:``, and ``source:`` are
    all supported by Google News RSS and can be included in ``query``.
    """

    query: str
    language: str = "en"
    country: str = "US"
    category: str = "General"
    priority: int = 2
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class HackerNewsConfig(BaseModel):
    """A Hacker News feed fetched via the public Firebase JSON API."""

    feed: str = "top"
    max_items: int = Field(default=20, ge=1, le=100)
    min_score: int = Field(default=50, ge=0)
    category: str = "General"
    priority: int = 2
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class RedditConfig(BaseModel):
    """A subreddit feed fetched via the public Reddit JSON API."""

    subreddit: str
    sort: str = "hot"
    time_filter: str = "day"
    max_items: int = Field(default=20, ge=1, le=100)
    min_score: int = Field(default=10, ge=0)
    category: str = "General"
    priority: int = 2
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class GitHubReleasesConfig(BaseModel):
    """GitHub releases tracked via the public Atom feed for a repository."""

    repo: str
    category: str = "General"
    priority: int = 2
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class PodcastConfig(BaseModel):
    """A podcast tracked via its RSS/Atom feed URL."""

    feed_url: str
    name: str = ""
    category: str = "General"
    priority: int = 2
    hide_keywords: list[str] = Field(default_factory=list)
    highlight_keywords: list[str] = Field(default_factory=list)
    require_keywords: list[str] = Field(default_factory=list)


class RelevanceConfig(BaseModel):
    initial_keywords: dict[str, list[str]] = Field(
        default_factory=lambda: {"high": [], "medium": []},
    )
    min_ratings_for_learning: int = 5
    tfidf_preference_weight: float = 0.35
    category_preference_weight: float = 0.6
    source_preference_weight: float = 0.3
    rating_decay_half_life_days: int = 30
    implicit_signal_weight: float = 0.5
    topic_synonyms: dict[str, list[str]] = Field(default_factory=dict)

    embedding_provider: Literal["ollama", "openrouter", "openai", "off"] = "off"
    # Embedding model name. For Ollama: "nomic-embed-text". For OpenRouter:
    # "openai/text-embedding-3-small". For OpenAI-compat: model name on that server.
    embedding_model: str = "nomic-embed-text"
    # Weight of the embedding cosine-similarity signal in the score breakdown.
    embedding_preference_weight: float = 0.5
    # Remove cross-source articles that cover the same story using embedding
    # cosine similarity. Only active when embedding_provider != "off".
    semantic_dedup_enabled: bool = True
    semantic_dedup_threshold: float = 0.85

    topic_score_weight: float = 0.3

    llm_rerank_enabled: bool = False
    # Model for reranking. Empty string = use the summarizer model.
    llm_rerank_model: str = ""
    # Number of top candidates to rerank per digest run.
    llm_rerank_top_k: int = 30
    # Blend weight: final_score = (1-blend)*classical + blend*llm_score.
    llm_rerank_blend: float = 0.4


class YouTubeTranscriptionConfig(BaseModel):
    """Settings for audio-based YouTube transcription via OpenRouter Whisper."""

    enabled: bool = False
    model: str = "openai/whisper-large-v3-turbo"
    max_duration_seconds: int = Field(default=1800, ge=60, le=7200)


class OutputConfig(BaseModel):
    format: str = "both"
    path: str = "data/digests"


class LlmConfig(BaseModel):
    provider: str = "openrouter"
    ollama_host: str = "http://localhost:11434"
    manage_lifecycle: bool = True
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3.5-flash-02-23"
    openrouter_daily_budget_usd: float = 1.0
    openrouter_monthly_budget_usd: float = 10.0
    openrouter_pick_cheapest: bool = False
    # OpenAI-compatible endpoint (provider: "openai")
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""


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
    # Case-insensitive substrings; articles whose title or description contains
    # any of these phrases are dropped before ranking. Empty list = no filter.
    exclude_keywords: list[str] = Field(
        default_factory=lambda: [
            "Community Forum",
            "promotional code",
            "promotional campaign",
        ],
    )
    # LLM summarization tuning.
    max_key_takeaways: int = Field(default=5, ge=1, le=10)
    max_summary_paragraphs: int = Field(default=5, ge=1, le=10)
    # Number of articles to summarize concurrently. Higher = faster but more
    # likely to hit provider rate limits. Set to 1 to disable concurrency.
    summarize_workers: int = Field(default=4, ge=1, le=16)
    # Language for digest output. ISO 639-1 code (e.g. "en", "fr", "de") or
    # "source" to auto-detect each article's language and summarize in that
    # language. Default "en" preserves the original English-only behaviour.
    digest_language: str = "en"
    # schedule.times: list of "HH:MM" strings; schedule.timezone: IANA name.
    # Using dict[str, Any] because 'timezone' is a plain string, not a list.
    schedule: dict[str, Any] = Field(
        default_factory=lambda: {"times": ["07:00", "18:00"]},
    )
    feeds: list[FeedConfig] = Field(default_factory=list)
    youtube_channels: list[YouTubeChannelConfig] = Field(default_factory=list)
    watch_urls: list[WatchUrlConfig] = Field(default_factory=list)
    relevance: RelevanceConfig = Field(default_factory=RelevanceConfig)
    youtube_transcription: YouTubeTranscriptionConfig = Field(
        default_factory=YouTubeTranscriptionConfig
    )
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
        logger.debug("python-dotenv not installed; skipping .env load")
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

    if os.environ.get("OPENAI_API_BASE_URL"):
        expanded.setdefault("llm", {})["openai_base_url"] = os.environ[
            "OPENAI_API_BASE_URL"
        ]
    if os.environ.get("OPENAI_API_KEY"):
        expanded.setdefault("llm", {})["openai_api_key"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("OPENAI_MODEL"):
        expanded.setdefault("llm", {})["openai_model"] = os.environ["OPENAI_MODEL"]

    cap = os.environ.get("CONDENSEIT_MAX_ARTICLES_PER_DIGEST", "").strip()
    if cap:
        try:
            expanded["max_articles_per_digest"] = int(cap)
        except ValueError:
            logger.debug(
                "Ignoring invalid CONDENSEIT_MAX_ARTICLES_PER_DIGEST=%r",
                cap,
            )

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
