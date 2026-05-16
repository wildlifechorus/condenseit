"""Main digest pipeline orchestration."""

from __future__ import annotations

import json
import logging
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import markdown

from condenseit.advisor.model_advisor import ModelAdvisor
from condenseit.collectors.rss import RSSCollector
from condenseit.collectors.website import check_website_changes_with_health
from condenseit.collectors.youtube import YouTubeCollector
from condenseit.config import AppConfig, load_config, resolve_output_path
from condenseit.learning.preference_engine import PreferenceEngine
from condenseit.pipeline.article_balance import select_balanced_digest_articles
from condenseit.providers.base import SummarizerProvider
from condenseit.providers.factory import build_summarizer
from condenseit.ratings_import import apply_configured_ratings_import
from condenseit.read_import import apply_configured_read_import
from condenseit.services.deploy import VpsDeployer
from condenseit.services.notifications import send_digest_email
from condenseit.settings_overlay import apply_db_settings
from condenseit.store.database import ContentStore
from condenseit.store.secure_keys import SecureKeyStore
from condenseit.store.sources import SourceRegistry

logger = logging.getLogger(__name__)

_APP_CSS = Path(__file__).resolve().parent.parent / "web" / "static" / "app.css"


class DigestPipeline:
    def __init__(self, config_path: str | None = None) -> None:
        self.config: AppConfig = load_config(config_path)
        self.store = ContentStore()
        self.config = apply_db_settings(self.config, self.store)
        self.sources = SourceRegistry(self.store)
        self.sources.seed_from_config(self.config)
        self.summarizer: SummarizerProvider = build_summarizer(self.config, self.store)
        self.preferences = PreferenceEngine(
            self.store,
            self.config.relevance.min_ratings_for_learning,
            self.config.relevance.tfidf_preference_weight,
            self.config.relevance.category_preference_weight,
            self.config.relevance.source_preference_weight,
            self.config.relevance.rating_decay_half_life_days,
        )
        self.digest_md = ""
        self.digest_html = ""
        self.stats: dict[str, Any] = {}

    def run(self, *, dry_run: bool = False) -> dict[str, Any]:
        start = time.time()
        logger.info("Starting digest pipeline")

        imported = apply_configured_ratings_import(self.store, self.config)
        if imported:
            logger.info("Ratings sidecar import applied %d upserts", imported)

        read_imported = apply_configured_read_import(self.store, self.config)
        if read_imported:
            logger.info("Read sidecar import applied %d URL(s)", read_imported)

        feeds = self.sources.feeds_for_config() or self.config.feeds
        youtube = self.sources.youtube_for_config() or self.config.youtube_channels
        watch = self.sources.watch_for_config() or self.config.watch_urls

        rss = RSSCollector(feeds)
        articles: list[dict[str, Any]] = []
        for _feed, items, err in rss.collect_feed_results():
            for a in items:
                articles.append(a.to_dict())
            self.sources.record_health(
                _feed.url,
                status="ok" if err is None else "error",
                error=err,
                item_count=len(items),
            )

        yt = YouTubeCollector(youtube, self.store)
        videos, yt_health = yt.collect_new_videos_with_health()
        for rss_url, err, count in yt_health:
            self.sources.record_health(
                rss_url,
                status="ok" if err is None else "error",
                error=err,
                item_count=count,
            )

        changes, web_health = check_website_changes_with_health(watch, self.store)
        for url, err, nbytes in web_health:
            self.sources.record_health(
                url,
                status="ok" if err is None else "error",
                error=err,
                item_count=nbytes,
            )

        for v in videos:
            articles.append(v.to_dict())

        # Persist new articles and identify the truly fresh subset.
        fresh = self.store.deduplicate(articles)

        # Accumulate the full same-day pool so that re-runs on the same day
        # distil *all* articles collected today rather than only the net-new
        # batch (which shrinks toward zero with each subsequent run).
        today_midnight = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        todays_articles = self.store.articles_collected_since(today_midnight)

        if todays_articles:
            # DB rows already include the just-saved fresh items; use the full
            # today set so subsequent same-day digests cover everything seen
            # since midnight, not just what arrived in this specific run.
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

        keywords = self.config.relevance.initial_keywords
        ranked = self.preferences.rank_articles(
            articles,
            keyword_high={k.lower() for k in keywords.get("high", [])},
            keyword_medium={k.lower() for k in keywords.get("medium", [])},
        )
        max_n = self.config.max_articles_per_digest
        if self.config.balance_digest_categories:
            ranked = select_balanced_digest_articles(
                ranked, max_n, self.config.max_articles_per_category
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
            for art in ranked:
                category = str(art.get("category", "General"))
                summary = self.summarizer.summarize_article(art)
                is_video = art["url"] in video_urls
                entry = {
                    "title": art["title"],
                    "url": art["url"],
                    "summary": summary,
                    "source": str(art.get("source", "")),
                    "category": category,
                    "published_at": str(art.get("published_at") or ""),
                    "kind": "video" if is_video else "article",
                }
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
            "digest_items": digest_items,
        }
        self._save_outputs()
        self.store.save_digest(
            self.digest_md,
            self.digest_html,
            json.dumps(self.stats),
        )
        logger.info("Digest complete in %s", self.stats["processing_time"])
        if not dry_run:
            self._maybe_weekly_advisor()
        return self.stats

    def _filter_by_age(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
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
            raw = str(art.get('published_at') or '').strip()
            if not raw:
                # No publish date available; keep it.
                kept.append(art)
                continue
            try:
                pub = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=UTC)
            except ValueError:
                # Unparseable date; keep it to avoid silent data loss.
                kept.append(art)
                continue

            if pub >= cutoff:
                kept.append(art)
            else:
                dropped += 1

        if dropped:
            logger.info(
                'Age filter (%dh cutoff): dropped %d old article(s), %d remaining',
                max_hours,
                dropped,
                len(kept),
            )
        return kept

    def _filter_read(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Exclude articles the user has already marked as read.

        Only articles explicitly marked read are removed. Unread articles that
        fall within the age window continue to appear in subsequent digests.
        """
        read_urls = self.store.get_read_urls()
        if not read_urls:
            return articles
        kept = [a for a in articles if a.get("url") not in read_urls]
        dropped = len(articles) - len(kept)
        if dropped:
            logger.info(
                "Read filter: excluded %d already-read article(s), %d remaining",
                dropped,
                len(kept),
            )
        return kept

    def _maybe_weekly_advisor(self) -> None:
        """At most once per week, store a model recommendation snapshot."""
        last = self.store.get_setting("advisor_weekly_last", "")
        now = datetime.now(UTC)
        if last:
            try:
                prev = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if prev.tzinfo is None:
                    prev = prev.replace(tzinfo=UTC)
                if now - prev < timedelta(days=7):
                    return
            except ValueError:
                pass
        cur = self.store.get_setting("model", self.config.model)
        rec = ModelAdvisor(self.store, self.config.llm.ollama_host).recommend(cur)
        self.store.set_setting("advisor_weekly_last", now.isoformat())
        self.store.set_setting(
            "advisor_weekly_recommendation",
            json.dumps(rec, default=str),
        )
        logger.info(
            "Weekly advisor snapshot: %s",
            rec.get("recommended_model"),
        )

    def post_run(
        self,
        *,
        skip_email: bool = False,
        skip_deploy: bool = False,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        keys = SecureKeyStore(self.store)

        if skip_email:
            results["email"] = {
                "status": "skipped",
                "reason": "digest run requested skip email",
            }
        else:
            results["email"] = send_digest_email(
                self.config.email,
                keys,
                digest_md=self.digest_md,
                digest_html=self.digest_html,
                stats=self.stats,
                digest_url=self.config.vps.digest_url,
            )

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
            items.append(
                {
                    "id": i,
                    "title": str(art.get("title", "")),
                    "url": u,
                    "summary": "",
                    "source": str(art.get("source", "")),
                    "category": str(art.get("category", "General")),
                    "published_at": str(art.get("published_at") or ""),
                    "kind": "video" if u in video_urls else "article",
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
