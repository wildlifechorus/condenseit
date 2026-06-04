"""Main digest pipeline orchestration."""

import json
import logging
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Self

import markdown
import numpy as np

from condenseit.collectors.github_releases import GitHubReleasesCollector
from condenseit.collectors.google_news import GoogleNewsCollector
from condenseit.collectors.hackernews import HackerNewsCollector
from condenseit.collectors.podcast import PodcastCollector
from condenseit.collectors.reddit import RedditCollector
from condenseit.collectors.rss import RSSCollector
from condenseit.collectors.website import check_website_changes_with_health
from condenseit.collectors.youtube import YouTubeCollector
from condenseit.config import AppConfig, load_config, resolve_output_path
from condenseit.learning.embeddings import (
    build_embedding_provider,
    cosine_similarity,
    get_or_compute_embedding,
)
from condenseit.learning.preference_engine import PreferenceEngine
from condenseit.learning.reranker import build_profile_narrative, rerank
from condenseit.pipeline.article_balance import select_balanced_digest_articles
from condenseit.providers.base import SummarizerProvider
from condenseit.providers.budget import BudgetTracker
from condenseit.providers.factory import build_summarizer
from condenseit.services.deploy import VpsDeployer
from condenseit.settings_overlay import apply_db_settings
from condenseit.store.database import ContentStore
from condenseit.store.secure_keys import SecureKeyStore
from condenseit.store.sources import SourceRegistry

logger = logging.getLogger(__name__)

_APP_CSS = Path(__file__).resolve().parent.parent / "web" / "static" / "app.css"


def _keyword_matches_text(keyword: str, text: str) -> bool:
    """Match a single keyword against lowercased combined text.

    Supports a ``*`` wildcard anywhere in the keyword:
    - ``CVE-*``  matches any text containing ``cve-``
    - ``*patch*`` matches any text containing ``patch``
    - Plain text (no ``*``) is a case-insensitive substring match.
    """
    kw = keyword.strip().lower()
    if not kw:
        return False
    if "*" not in kw:
        return kw in text
    # Split on * and require every non-empty part to appear in the text.
    # This is not order-aware but covers CVE-*, GHSA-*, *word* patterns.
    parts = [p for p in kw.split("*") if p]
    return all(p in text for p in parts)


def _article_matches_keywords(article: dict[str, Any], keywords: list[str]) -> bool:
    """Return True if any keyword matches the article title or content snippet."""
    if not keywords:
        return False
    title = str(article.get("title") or "").lower()
    content = str(article.get("content") or article.get("description") or "")[
        :500
    ].lower()
    combined = title + " " + content
    return any(_keyword_matches_text(kw, combined) for kw in keywords)


def _apply_source_rules(
    articles: list[dict[str, Any]],
    hide_keywords: list[str],
    highlight_keywords: list[str],
    require_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter and tag articles according to per-source keyword rules.

    - ``hide_keywords``: article is dropped if any keyword matches.
    - ``require_keywords``: article is dropped if the list is non-empty and
      none of the keywords match (allowlist mode).
    - ``highlight_keywords``: article is tagged for a score boost if any
      keyword matches.
    """
    out: list[dict[str, Any]] = []
    for art in articles:
        if _article_matches_keywords(art, hide_keywords):
            continue
        if require_keywords and not _article_matches_keywords(art, require_keywords):
            continue
        if highlight_keywords and _article_matches_keywords(art, highlight_keywords):
            art["_highlight_boost"] = True
        out.append(art)
    return out


class DigestPipeline:
    def __init__(self, config_path: str | None = None) -> None:
        self.config: AppConfig = load_config(config_path)
        self.store = ContentStore()
        self.config = apply_db_settings(self.config, self.store)
        self.sources = SourceRegistry(self.store)
        self.sources.seed_from_config(self.config)
        self.digest_run_id = uuid.uuid4().hex
        self.summarizer: SummarizerProvider = build_summarizer(
            self.config,
            self.store,
            digest_run_id=self.digest_run_id,
        )
        _keys = SecureKeyStore(self.store)
        self._or_key: str = (
            _keys.get_key("openrouter") or self.config.llm.openrouter_api_key or ""
        )
        self._ai_budget: BudgetTracker | None = (
            BudgetTracker(
                self.store,
                self.config.llm.openrouter_daily_budget_usd,
                self.config.llm.openrouter_monthly_budget_usd,
                digest_run_id=self.digest_run_id,
            )
            if self._or_key
            else None
        )
        self._embed_provider = build_embedding_provider(
            self.config.relevance.embedding_provider,
            self.config.relevance.embedding_model,
            self.config.llm.ollama_host,
            self._or_key,
            openai_base_url=self.config.llm.openai_base_url,
            openai_api_key=self.config.llm.openai_api_key,
            budget=self._ai_budget,
        )
        self.preferences = PreferenceEngine(
            self.store,
            self.config.relevance.min_ratings_for_learning,
            self.config.relevance.tfidf_preference_weight,
            self.config.relevance.category_preference_weight,
            self.config.relevance.source_preference_weight,
            self.config.relevance.rating_decay_half_life_days,
            self.config.relevance.implicit_signal_weight,
            self.config.relevance.topic_synonyms,
            embedding_provider=self._embed_provider,
            embedding_weight=self.config.relevance.embedding_preference_weight,
            topic_score_weight=self.config.relevance.topic_score_weight,
        )
        self.digest_md = ""
        self.digest_html = ""
        self.stats: dict[str, Any] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Explicitly close the pipeline's database connection.

        Always call this (or use DigestPipeline as a context manager) when
        the pipeline is done. Leaving the connection open keeps a SQLite
        writer lock alive that blocks every write on the shared web-server
        connection, causing 500s on /api/read, /api/dismiss, and other
        write endpoints.
        """
        self.store.close()

    def _record_health(
        self,
        health: list[tuple[str, str | None, int]],
    ) -> None:
        for url, err, count in health:
            self.sources.record_health(
                url,
                status="ok" if err is None else "error",
                error=err,
                item_count=count,
            )

    def run(self, *, dry_run: bool = False) -> dict[str, Any]:
        start = time.time()
        logger.info("Starting digest pipeline")

        feeds = self.sources.feeds_for_config() or self.config.feeds
        youtube = self.sources.youtube_for_config() or self.config.youtube_channels
        watch = self.sources.watch_for_config() or self.config.watch_urls
        gnews = self.sources.google_news_for_config()
        hackernews = self.sources.hackernews_for_config()
        reddit = self.sources.reddit_for_config()
        github_releases = self.sources.github_releases_for_config()
        podcasts = self.sources.podcast_sources_for_config()

        rss = RSSCollector(feeds)
        articles: list[dict[str, Any]] = []
        for _feed, items, err in rss.collect_feed_results():
            articles.extend(
                _apply_source_rules(
                    [a.to_dict() for a in items],
                    _feed.hide_keywords,
                    _feed.highlight_keywords,
                    _feed.require_keywords,
                )
            )
            self.sources.record_health(
                _feed.url,
                status="ok" if err is None else "error",
                error=err,
                item_count=len(items),
            )

        yt = YouTubeCollector(
            youtube,
            self.store,
            transcription_config=self.config.youtube_transcription,
            openrouter_api_key=self._or_key,
            budget=self._ai_budget,
        )
        videos, yt_health = yt.collect_new_videos_with_health()
        self._record_health(yt_health)

        changes, web_health = check_website_changes_with_health(watch, self.store)
        self._record_health(web_health)

        for cfg in gnews:
            src_articles, src_health = GoogleNewsCollector(
                [cfg],
            ).collect_all_with_health()
            articles.extend(
                _apply_source_rules(
                    src_articles,
                    cfg.hide_keywords,
                    cfg.highlight_keywords,
                    cfg.require_keywords,
                )
            )
            self._record_health(src_health)

        for cfg in hackernews:
            src_articles, src_health = HackerNewsCollector(
                [cfg],
            ).collect_all_with_health()
            articles.extend(
                _apply_source_rules(
                    src_articles,
                    cfg.hide_keywords,
                    cfg.highlight_keywords,
                    cfg.require_keywords,
                )
            )
            self._record_health(src_health)

        for cfg in reddit:
            src_articles, src_health = RedditCollector(
                [cfg],
            ).collect_all_with_health()
            articles.extend(
                _apply_source_rules(
                    src_articles,
                    cfg.hide_keywords,
                    cfg.highlight_keywords,
                    cfg.require_keywords,
                )
            )
            self._record_health(src_health)

        for cfg in github_releases:
            src_articles, src_health = GitHubReleasesCollector(
                [cfg],
            ).collect_all_with_health()
            articles.extend(
                _apply_source_rules(
                    src_articles,
                    cfg.hide_keywords,
                    cfg.highlight_keywords,
                    cfg.require_keywords,
                )
            )
            self._record_health(src_health)

        for cfg in podcasts:
            src_articles, src_health = PodcastCollector(
                [cfg],
            ).collect_all_with_health()
            articles.extend(
                _apply_source_rules(
                    src_articles,
                    cfg.hide_keywords,
                    cfg.highlight_keywords,
                    cfg.require_keywords,
                )
            )
            self._record_health(src_health)

        articles.extend(v.to_dict() for v in videos)

        # Persist new articles and identify the truly fresh subset.
        fresh = self.store.deduplicate(articles)

        today_midnight = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        todays_articles = self.store.articles_collected_since(today_midnight)

        if todays_articles:
            articles = todays_articles
            logger.info(
                "Same-day accumulation: %d articles collected today"
                " (%d net-new this run)",
                len(todays_articles),
                len(fresh),
            )
        else:
            articles = fresh

        articles = self._filter_by_age(articles)
        articles = self._filter_read(articles)
        articles = self._filter_by_language(articles)
        articles = self._filter_by_excluded_keywords(articles)

        keywords = self.config.relevance.initial_keywords
        ranked = self.preferences.rank_articles(
            articles,
            keyword_high={k.lower() for k in keywords.get("high", [])},
            keyword_medium={k.lower() for k in keywords.get("medium", [])},
            keyword_negative=(
                # Explicit user list (bootstrap_dislikes / Admin UI)
                {
                    k.lower()
                    for k in self.config.relevance.disliked_keywords
                    if k.strip()
                }
                # High-frequency terms learned from 1-2 star ratings so the
                # profile's disliked vocabulary automatically strengthens the
                # keyword penalty without requiring manual list maintenance.
                | self.preferences.learned_disliked_keywords()
            ),
        )
        # Apply per-source highlight boost before dedup so highlighted articles
        # are more likely to win their story cluster.
        for art in ranked:
            if art.get("_highlight_boost"):
                art["preference_score"] = art.get("preference_score", 0.0) + 2.0
                art["highlighted"] = True

        # Deduplicate after ranking so the highest-scoring version of each
        # story cluster is the one that survives.
        ranked = self._deduplicate_stories(ranked)

        if self.config.relevance.llm_rerank_enabled and not dry_run:
            profile_narrative = build_profile_narrative(
                self.preferences,
                profile_summary=self.config.relevance.profile_summary,
                extra_dislikes=list(
                    {k for k in self.config.relevance.disliked_keywords if k.strip()}
                    | self.preferences.learned_disliked_keywords()
                ),
            )
            if profile_narrative:
                _rerank_model = (
                    self.config.relevance.llm_rerank_model or self.summarizer.model_name
                )
                _api_key = self._or_key or None
                # OpenAI-compat reranking: used when no OpenRouter key and
                # llm.provider is "openai" with a configured base URL.
                _openai_base_url: str | None = None
                _openai_api_key: str = ""
                if (
                    not _api_key
                    and self.config.llm.provider == "openai"
                    and self.config.llm.openai_base_url
                ):
                    _openai_base_url = self.config.llm.openai_base_url
                    _openai_api_key = self.config.llm.openai_api_key
                _ollama = (
                    self.config.llm.ollama_host
                    if not _api_key and not _openai_base_url
                    else None
                )
                ranked = rerank(
                    ranked,
                    profile_narrative,
                    model=_rerank_model,
                    api_key=_api_key,
                    ollama_host=_ollama,
                    openai_base_url=_openai_base_url,
                    openai_api_key=_openai_api_key,
                    top_k=self.config.relevance.llm_rerank_top_k,
                    blend=self.config.relevance.llm_rerank_blend,
                    budget=self._ai_budget,
                )
                logger.info("LLM reranker applied (model=%s)", _rerank_model)

        max_n = self.config.max_articles_per_digest
        if self.config.balance_digest_categories:
            rel = self.config.relevance
            # Learned per-category preference (explicit + implicit) so the
            # balancer stops force-feeding categories the reader dislikes. Only
            # categories with enough rating evidence are eligible for gating, so
            # a stated-interest category with a couple of early bad ratings is
            # not permanently buried before it can be re-rated.
            all_scores = self.preferences.combined_category_scores()
            rating_counts = self.preferences.category_rating_counts()
            category_scores = {
                cat: score
                for cat, score in all_scores.items()
                if rating_counts.get(cat, 0) >= rel.category_min_ratings
            }
            ranked = select_balanced_digest_articles(
                ranked,
                max_n,
                self.config.max_articles_per_category,
                category_scores=category_scores,
                exclude_threshold=rel.category_exclude_threshold,
                demote_threshold=rel.category_demote_threshold,
                demote_cap=rel.category_demote_cap,
            )
        else:
            ranked = ranked[:max_n]

        logger.info(
            "%d articles, %d videos, %d changes, summarizing %d",
            len(articles),
            len(videos),
            len(changes),
            len(ranked),
        )

        categorized: dict[str, list[dict[str, Any]]] = {}
        video_summaries: list[dict[str, Any]] = []
        video_urls = {v.url for v in videos}

        if not dry_run:
            workers = self.config.summarize_workers
            logger.info(
                "Summarizing %d articles with %d concurrent worker(s)",
                len(ranked),
                workers,
            )
            # Parallelize LLM API calls (the bottleneck). executor.map preserves
            # input order so zip(ranked, summaries) pairs correctly.
            with ThreadPoolExecutor(max_workers=workers) as pool:
                summaries = list(pool.map(self.summarizer.summarize_article, ranked))

            # Process results sequentially to keep DB writes off worker threads.
            for art, result in zip(ranked, summaries):
                category = str(art.get("category", "General"))
                is_video = art["url"] in video_urls
                entry_kind = "video" if is_video else str(art.get("kind") or "article")
                entry = {
                    "title": art["title"],
                    "url": art["url"],
                    "summary": result["summary"],
                    "tldr": result["tldr"],
                    "key_takeaways": result["key_takeaways"],
                    "source": str(art.get("source", "")),
                    "category": category,
                    "published_at": str(art.get("published_at") or ""),
                    "kind": entry_kind,
                    "preference_score": art.get("preference_score"),
                    "score_breakdown": art.get("score_breakdown"),
                    "image_url": art.get("image_url"),
                    "topics": result.get("topics") or [],
                    "entities": result.get("entities") or [],
                    "novelty": result.get("novelty") or 0,
                    "relevance_to_you": result.get("relevance_to_you") or "",
                }
                # Persist enrichment so PreferenceEngine can use topics on next run.
                try:
                    self.store.save_enrichment(
                        url=art["url"],
                        topics=result.get("topics") or [],
                        entities=result.get("entities") or [],
                        novelty=result.get("novelty") or 0,
                        signals=result.get("relevance_signals") or [],
                        model=self.summarizer.model_name,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to persist enrichment for %s: %s",
                        art["url"],
                        exc,
                    )
                if is_video:
                    video_summaries.append(entry)
                else:
                    categorized.setdefault(category, []).append(entry)

            self.digest_md = self.summarizer.generate_digest(
                categorized,
                changes,
                video_summaries or None,
            )
        else:
            self.digest_md = self._dry_run_markdown(ranked, changes, len(videos))

        self.digest_html = markdown.markdown(
            self.digest_md,
            extensions=["tables", "fenced_code"],
        )
        elapsed = time.time() - start
        if dry_run:
            digest_items = self._digest_items_dry_run(ranked, video_urls, changes)
        else:
            digest_items = self._build_digest_items_ordered(
                categorized,
                video_summaries,
                changes,
            )

        self.stats = {
            "articles_count": len(ranked),
            "videos_count": len(videos),
            "changes_count": len(changes),
            "processing_time": f"{elapsed:.0f}s",
            "model": self.summarizer.model_name,
            "dry_run": dry_run,
            "cost_usd": 0.0,
            "digest_items": digest_items,
        }
        self._save_outputs()
        digest_id = self.store.save_digest(
            self.digest_md,
            self.digest_html,
            json.dumps(self.stats),
        )
        if not dry_run:
            self.store.attach_spending_to_digest(self.digest_run_id, digest_id)
            self.stats["cost_usd"] = self.store.sum_spending_for_digest(digest_id)
            self.store.update_digest_stats(digest_id, json.dumps(self.stats))
        logger.info("Digest complete in %s", self.stats["processing_time"])
        return self.stats

    def _filter_by_age(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Drop articles whose published_at is older than max_article_age_hours.

        Items with no parseable published_at are kept so that website-watcher
        changes (which have no publish date) are never accidentally dropped.
        """
        max_hours = self.config.max_article_age_hours
        if max_hours <= 0:
            return articles

        cutoff = datetime.now(UTC) - timedelta(hours=max_hours)
        kept: list[dict[str, Any]] = []
        dropped = 0

        for art in articles:
            raw = str(art.get("published_at") or "").strip()
            if not raw:
                kept.append(art)
                continue
            try:
                pub = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=UTC)
            except ValueError:
                kept.append(art)
                continue

            if pub >= cutoff:
                kept.append(art)
            else:
                dropped += 1

        if dropped:
            logger.info(
                "Age filter (%dh cutoff): dropped %d old article(s), %d remaining",
                max_hours,
                dropped,
                len(kept),
            )
        return kept

    def _filter_read(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Exclude articles the user has already marked as read.

        Three layers of matching (most to least strict):

        1. Exact URL match.
        2. Exact title match (case-insensitive) -- catches the same article
           re-appearing under a rotated URL (e.g. Google News opaque redirects)
           or dual URL paths on the same publisher.
        3. Fuzzy title match via Jaccard word-set similarity >= 0.35 -- catches
           cross-source duplicates where different publications cover the same
           story with similar but not identical headlines (e.g. "Turla Turns
           Kazuar Backdoor Into P2P Botnet" vs "Russian hackers turn Kazuar
           backdoor into modular P2P botnet").
        """
        read_urls = self.store.get_read_urls()
        read_titles = self.store.get_read_titles()
        if not read_urls and not read_titles:
            return articles

        # Pre-compute word sets for read titles to avoid repeated work.
        read_title_word_sets: list[frozenset[str]] = [
            frozenset(t.split()) for t in read_titles if t
        ]

        _jaccard_threshold = 0.35

        def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
            union = a | b
            if not union:
                return 0.0
            return len(a & b) / len(union)

        def _is_read(a: dict[str, Any]) -> bool:
            if a.get("url") in read_urls:
                return True
            if not read_titles:
                return False
            title = str(a.get("title", "")).lower().strip()
            if not title:
                return False
            # Exact match.
            if title in read_titles:
                return True
            # Fuzzy match against each read title's word set.
            words = frozenset(title.split())
            if len(words) < 3:
                # Too short to fuzzy-match reliably; avoid false positives.
                return False
            return any(
                _jaccard(words, rws) >= _jaccard_threshold
                for rws in read_title_word_sets
                if len(rws) >= 3
            )

        kept = [a for a in articles if not _is_read(a)]
        dropped = len(articles) - len(kept)
        if dropped:
            logger.info(
                "Read filter: excluded %d already-read article(s), %d remaining",
                dropped,
                len(kept),
            )
        return kept

    def _filter_by_language(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Drop articles whose detected language is not in preferred_languages.

        If preferred_languages is empty, all articles are kept. Detection
        failures always keep the article to avoid silent data loss.
        """
        preferred = self.config.preferred_languages
        if not preferred:
            return articles

        try:
            import langdetect
        except ImportError:
            logger.warning("langdetect not installed; skipping language filter.")
            return articles

        preferred_set = {lang.lower() for lang in preferred}
        kept: list[dict[str, Any]] = []
        dropped = 0

        for art in articles:
            text = (
                str(art.get("title") or "") + " " + str(art.get("content") or "")[:300]
            ).strip()
            if not text:
                kept.append(art)
                continue
            try:
                detected = langdetect.detect(text).lower()
                if detected in preferred_set:
                    kept.append(art)
                else:
                    dropped += 1
            except Exception:
                # Keep article when detection is uncertain.
                kept.append(art)

        if dropped:
            logger.info(
                "Language filter (%s): dropped %d article(s), %d remaining",
                ", ".join(preferred),
                dropped,
                len(kept),
            )
        return kept

    def _filter_by_excluded_keywords(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Drop articles whose title or description contains an excluded phrase.

        Each entry in ``config.exclude_keywords`` is treated as a
        case-insensitive substring match against the article title and the
        first 500 characters of its description/content field.  An empty
        list disables the filter entirely.
        """
        raw_phrases = self.config.exclude_keywords
        if not raw_phrases:
            return articles

        # Normalise once so we do cheap lower() comparisons in the loop.
        phrases = [p.lower() for p in raw_phrases if p.strip()]
        if not phrases:
            return articles

        kept: list[dict[str, Any]] = []
        dropped = 0

        for art in articles:
            title = str(art.get("title") or "").lower()
            description = str(art.get("description") or art.get("content") or "")[
                :500
            ].lower()
            combined = title + " " + description

            if any(phrase in combined for phrase in phrases):
                dropped += 1
            else:
                kept.append(art)

        if dropped:
            logger.info(
                "Keyword exclusion filter: dropped %d article(s) matching"
                " %r, %d remaining",
                dropped,
                raw_phrases,
                len(kept),
            )
        return kept

    def _deduplicate_stories(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove cross-source duplicates from an already-ranked article list.

        Pass 1 - Jaccard title similarity: skips any article whose title word
        set overlaps >= 0.35 with an already-kept article.  Titles shorter than
        3 words are never fuzzy-matched to avoid false positives.

        Pass 2 - Semantic embedding dedup (when an embedding provider is
        configured and ``semantic_dedup_enabled`` is true): embeds each
        surviving article and drops it if its cosine similarity to any
        already-kept embedding exceeds ``semantic_dedup_threshold``.
        Embeddings are fetched from the SQLite cache first so articles that
        were already embedded during preference scoring incur no extra cost.

        Because the input is already ranked, the highest-scoring version of
        each story cluster always survives both passes.
        """
        if not articles:
            return articles

        _jaccard_threshold = 0.35

        def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
            union = a | b
            return len(a & b) / len(union) if union else 0.0

        kept: list[dict[str, Any]] = []
        kept_word_sets: list[frozenset[str]] = []
        jaccard_dropped = 0

        for art in articles:
            title = str(art.get("title") or "").lower().strip()
            words = frozenset(title.split())
            if len(words) >= 3 and any(
                _jaccard(words, existing) >= _jaccard_threshold
                for existing in kept_word_sets
                if len(existing) >= 3
            ):
                jaccard_dropped += 1
                continue
            kept.append(art)
            kept_word_sets.append(words)

        if jaccard_dropped:
            logger.info(
                "Story dedup (Jaccard): removed %d near-duplicate(s)"
                " (threshold >= %.2f), %d remaining",
                jaccard_dropped,
                _jaccard_threshold,
                len(kept),
            )

        rel = self.config.relevance
        if (
            self._embed_provider is None
            or not rel.semantic_dedup_enabled
            or len(kept) < 2
        ):
            return kept

        sem_threshold = rel.semantic_dedup_threshold

        def _embed_article(art: dict[str, Any]):
            url = str(art.get("url") or "")
            content_hash = str(art.get("content_hash") or "")
            title_text = str(art.get("title") or "")
            body = str(art.get("content") or "")
            text = (title_text + " " + body[:500]).strip()
            try:
                vec = get_or_compute_embedding(
                    self._embed_provider,  # type: ignore[arg-type]
                    self.store,
                    url,
                    content_hash,
                    text,
                )
            except Exception:
                vec = None
            return art, vec

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_embed_article, kept))

        sem_kept: list[dict[str, Any]] = []
        kept_vecs: list[np.ndarray] = []
        sem_dropped = 0

        for art, vec in results:
            if vec is None:
                sem_kept.append(art)
                continue
            if any(cosine_similarity(vec, kv) >= sem_threshold for kv in kept_vecs):
                sem_dropped += 1
                continue
            sem_kept.append(art)
            kept_vecs.append(vec)

        if sem_dropped:
            logger.info(
                "Story dedup (semantic): removed %d near-duplicate(s)"
                " (cosine >= %.2f), %d remaining",
                sem_dropped,
                sem_threshold,
                len(sem_kept),
            )

        return sem_kept

    def post_run(
        self,
        *,
        skip_deploy: bool = False,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}

        if skip_deploy:
            results["deploy"] = {
                "status": "skipped",
                "reason": "digest run requested skip deploy",
            }
        else:
            out_dir = resolve_output_path(self.config)
            deployer = VpsDeployer(self.config.vps)
            results["deploy"] = deployer.deploy(out_dir)

        return results

    @staticmethod
    def _build_digest_items_ordered(
        categorized: dict[str, list[dict[str, Any]]],
        video_summaries: list[dict[str, Any]],
        changes: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Flatten digest entries for the web UI (same order as markdown)."""
        out: list[dict[str, Any]] = []
        n = 0
        for cat in sorted(categorized.keys()):
            for e in categorized[cat]:
                row = {**e, "id": n}
                n += 1
                out.append(row)
        for e in video_summaries:
            row = {**e, "id": n}
            n += 1
            out.append(row)
        for c in changes:
            status = str(c.get("status", "update"))
            out.append(
                {
                    "id": n,
                    "title": f"Website ({status})",
                    "url": str(c.get("url", "")),
                    "summary": str(c.get("snippet", ""))[:800],
                    "tldr": "",
                    "key_takeaways": [],
                    "source": "watch",
                    "category": str(c.get("category", "General")),
                    "published_at": "",
                    "kind": "watch",
                },
            )
            n += 1
        return out

    @staticmethod
    def _digest_items_dry_run(
        ranked: list[dict[str, Any]],
        video_urls: set[str],
        changes: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for i, art in enumerate(ranked):
            u = str(art.get("url", ""))
            item_kind = (
                "video" if u in video_urls else str(art.get("kind") or "article")
            )
            items.append(
                {
                    "id": i,
                    "title": str(art.get("title", "")),
                    "url": u,
                    "summary": "",
                    "tldr": "",
                    "key_takeaways": [],
                    "source": str(art.get("source", "")),
                    "category": str(art.get("category", "General")),
                    "published_at": str(art.get("published_at") or ""),
                    "kind": item_kind,
                    "preference_score": art.get("preference_score"),
                    "score_breakdown": art.get("score_breakdown"),
                    "image_url": art.get("image_url"),
                },
            )
        base = len(items)
        for j, c in enumerate(changes):
            status = str(c.get("status", "update"))
            items.append(
                {
                    "id": base + j,
                    "title": f"Website ({status})",
                    "url": str(c.get("url", "")),
                    "summary": str(c.get("snippet", ""))[:800],
                    "tldr": "",
                    "key_takeaways": [],
                    "source": "watch",
                    "category": str(c.get("category", "General")),
                    "published_at": "",
                    "kind": "watch",
                },
            )
        return items

    def _dry_run_markdown(
        self,
        articles: list[dict[str, str]],
        changes: list[dict[str, str]],
        video_count: int,
    ) -> str:
        lines = [
            f"# CondenseIt Dry Run — {datetime.now(UTC).isoformat()}",
            "",
            f"Collected **{len(articles)}** articles, **{video_count}** videos.",
            "",
        ]
        for art in articles:
            score = art.get("preference_score", "")
            lines.append(
                f"- [{art['title']}]({art['url']}) — {art['category']} ({score})",
            )
        if changes:
            lines.append("\n## Website changes\n")
            for c in changes:
                lines.append(f"- {c['status']}: {c['url']}")
        return "\n".join(lines)

    def _save_outputs(self) -> None:
        out_dir = resolve_output_path(self.config)
        if _APP_CSS.is_file():
            shutil.copy2(_APP_CSS, out_dir / "app.css")
        stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H%M")
        md_path = out_dir / f"digest_{stamp}.md"
        html_path = out_dir / f"digest_{stamp}.html"
        md_path.write_text(self.digest_md, encoding="utf-8")
        html_path.write_text(self._wrap_html(self.digest_html), encoding="utf-8")
        (out_dir / "latest.md").write_text(self.digest_md, encoding="utf-8")
        (out_dir / "latest.html").write_text(
            self._wrap_html(self.digest_html),
            encoding="utf-8",
        )

    @staticmethod
    def _wrap_html(body: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0d9488">
  <title>CondenseIt Digest</title>
  <link rel="stylesheet" href="app.css">
</head>
<body>
  <div class="layout layout--pwa">
    <main class="content content--pwa">
      <section class="digest-panel">
        <div class="digest-toolbar">
          <span class="digest-meta">
            Snapshot written next to this file as <code>latest.html</code>.
          </span>
        </div>
        <article class="prose digest-body">{body}</article>
      </section>
    </main>
  </div>
</body>
</html>"""
