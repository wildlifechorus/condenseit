"""Admin panel routes - Jinja2 HTML pages and JSON API endpoints."""

from __future__ import annotations

import json
import os
import re
import secrets
from typing import Any
from urllib.parse import quote, quote_plus

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)

from condenseit.config import load_config
from condenseit.providers.openrouter_models import pick_cheapest_text_model
from condenseit.services.ollama_client import (
    ollama_delete,
    ollama_list_tags,
    ollama_pull,
)
from condenseit.settings_overlay import apply_db_settings
from condenseit.store.database import ContentStore
from condenseit.store.opml import build_opml, parse_opml_outlines
from condenseit.store.secure_keys import SecureKeyStore
from condenseit.store.sources import SourceRegistry
from condenseit.web.templating import page_context, templates

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

_GNEWS_BASE = "https://news.google.com/rss/search"
_HN_BASE = "https://hacker-news.firebaseio.com/v0"

# Reddit's JSON/RSS endpoints are blocked on most VPS IPs. Any Reddit source
# is transparently converted to an equivalent Lemmy.world RSS feed so it still
# works without requiring Reddit API credentials.
_LEMMY_INSTANCE = "https://lemmy.world"
_REDDIT_HOST_RE = re.compile(r"(?:https?://)?(?:www\.|old\.)?reddit\.com/r/([^/?#\s]+)", re.IGNORECASE)


def _reddit_subreddit_to_lemmy_url(subreddit: str) -> str:
    """Return a Lemmy.world RSS feed URL equivalent to r/{subreddit}."""
    sub = subreddit.strip().lstrip("r/").lstrip("/").rstrip("/")
    return f"{_LEMMY_INSTANCE}/feeds/c/{sub}.xml?sort=Active&type_=All"


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def _build_source_extra(
    source_type: str,
    url: str,
    channel_id: str,
    name: str,
    *,
    query: str = "",
    language: str = "en",
    country: str = "US",
    hn_feed: str = "top",
    hn_max_items: int = 20,
    hn_min_score: int = 50,
    subreddit: str = "",
    reddit_sort: str = "hot",
    reddit_time_filter: str = "day",
    reddit_max_items: int = 20,
    reddit_min_score: int = 10,
    github_repo: str = "",
) -> tuple[dict[str, Any], str, str, str | None]:
    """Return ``(extra_json_dict, feed_url, effective_type, conversion_note)``

    ``effective_type`` may differ from ``source_type`` when a Reddit source is
    automatically converted to a Lemmy RSS feed. ``conversion_note`` is a
    human-readable explanation of the conversion, or ``None`` if no conversion
    occurred.
    """
    extra: dict[str, Any] = {}
    feed_url = url
    effective_type = source_type
    conversion_note: str | None = None

    if source_type == "youtube" and channel_id:
        extra = {"channel_id": channel_id, "handle": name}
        feed_url = (
            f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        )

    elif source_type == "google_news":
        lang = (language or "en").lower()
        ctry = (country or "US").upper()
        extra = {"query": query, "language": lang, "country": ctry}
        feed_url = (
            f"{_GNEWS_BASE}?q={quote_plus(query)}"
            f"&hl={lang}-{ctry}&gl={ctry}&ceid={ctry}:{lang}"
        )

    elif source_type == "hackernews":
        valid_feeds = {"top", "best", "new", "ask", "show"}
        feed = hn_feed if hn_feed in valid_feeds else "top"
        extra = {
            "feed": feed,
            "max_items": hn_max_items,
            "min_score": hn_min_score,
        }
        feed_url = f"{_HN_BASE}/{feed}stories.json"

    elif source_type == "reddit":
        # Reddit's API and RSS endpoints are blocked on datacenter IPs.
        # Store the source as type="reddit" so the badge still shows "Reddit"
        # in the UI, but point the URL at an equivalent Lemmy.world RSS feed.
        # feeds_for_config() picks up reddit sources with a converted_from key
        # and hands them to the RSS collector instead of the Reddit collector.
        sub = (subreddit or "").strip().lstrip("r/").lstrip("/")
        # Also try to extract subreddit from a pasted Reddit URL.
        if not sub and url:
            m = _REDDIT_HOST_RE.search(url)
            if m:
                sub = m.group(1)
        feed_url = _reddit_subreddit_to_lemmy_url(sub)
        # Keep effective_type="reddit" so the UI badge stays "Reddit".
        extra = {"converted_from": f"reddit:r/{sub}"}
        conversion_note = (
            f"r/{sub} automatically routed via Lemmy.world RSS "
            f"(Reddit's API is blocked on most server IPs). "
            f"Feed: {feed_url}"
        )

    elif source_type == "rss" and url and _REDDIT_HOST_RE.search(url):
        # User pasted a reddit.com URL into the RSS URL field - convert it too.
        m = _REDDIT_HOST_RE.search(url)
        sub = m.group(1) if m else ""
        if sub:
            feed_url = _reddit_subreddit_to_lemmy_url(sub)
            extra = {"converted_from": f"reddit:r/{sub}"}
            conversion_note = (
                f"Reddit URL detected and converted to a Lemmy.world RSS feed. "
                f"Feed: {feed_url}"
            )

    elif source_type == "github_releases":
        repo = (github_repo or "").strip().strip("/")
        extra = {"repo": repo}
        feed_url = f"https://github.com/{repo}/releases.atom"

    elif source_type == "podcast":
        extra = {"feed_url": url, "name": name}
        feed_url = url

    return extra, feed_url, effective_type, conversion_note


async def _read_source_payload(request: Request) -> dict[str, Any]:
    """Read source form or JSON payloads into one normalized shape."""
    ct = request.headers.get("content-type", "")
    if "multipart/form-data" in ct or "application/x-www-form-urlencoded" in ct:
        form = await request.form()

        def _fstr(key: str, default: str = "") -> str:
            return str(form.get(key, default)).strip()

        def _fint(key: str, default: int = 0) -> int:
            try:
                return int(form.get(key, default))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default

        return {
            "source_type": _fstr("source_type", "rss"),
            "name": _fstr("name"),
            "url": _fstr("url"),
            "category": _fstr("category", "General") or "General",
            "priority": _fint("priority", 2),
            "channel_id": _fstr("channel_id"),
            "query": _fstr("query"),
            "language": _fstr("language", "en") or "en",
            "country": _fstr("country", "US") or "US",
            "hn_feed": _fstr("hn_feed", "top") or "top",
            "hn_max_items": _fint("hn_max_items", 20),
            "hn_min_score": _fint("hn_min_score", 50),
            "subreddit": _fstr("subreddit"),
            "reddit_sort": _fstr("reddit_sort", "hot") or "hot",
            "reddit_time_filter": _fstr("reddit_time_filter", "day") or "day",
            "reddit_max_items": _fint("reddit_max_items", 20),
            "reddit_min_score": _fint("reddit_min_score", 10),
            "github_repo": _fstr("github_repo"),
        }

    body = await request.json()
    return {
        "source_type": str(body.get("source_type", "rss")).strip(),
        "name": str(body.get("name", "")).strip(),
        "url": str(body.get("url", "")).strip(),
        "category": str(body.get("category", "General")).strip() or "General",
        "priority": int(body.get("priority", 2)),
        "channel_id": str(body.get("channel_id", "")).strip(),
        "query": str(body.get("query", "")).strip(),
        "language": str(body.get("language", "en")).strip() or "en",
        "country": str(body.get("country", "US")).strip() or "US",
        "hn_feed": str(body.get("hn_feed", "top")).strip() or "top",
        "hn_max_items": int(body.get("hn_max_items", 20)),
        "hn_min_score": int(body.get("hn_min_score", 50)),
        "subreddit": str(body.get("subreddit", "")).strip(),
        "reddit_sort": str(body.get("reddit_sort", "hot")).strip() or "hot",
        "reddit_time_filter": str(body.get("reddit_time_filter", "day")).strip()
        or "day",
        "reddit_max_items": int(body.get("reddit_max_items", 20)),
        "reddit_min_score": int(body.get("reddit_min_score", 10)),
        "github_repo": str(body.get("github_repo", "")).strip(),
    }


def _source_payload_error(payload: dict[str, Any]) -> str | None:
    """Return an API-facing validation message for invalid source payloads."""
    if not payload["name"]:
        return "name field is required"
    if not 1 <= int(payload["priority"]) <= 5:
        return "priority must be between 1 and 5"
    return None


def create_admin_router(
    config_path: str | None,
    store: ContentStore | None = None,
) -> APIRouter:
    router = APIRouter()
    config = load_config(config_path)
    store = store or ContentStore()
    sources = SourceRegistry(store)
    sources.seed_from_config(config)
    keys = SecureKeyStore(store)

    def _digests() -> list[dict]:
        return store.list_digests(limit=12)

    def _merged():
        return apply_db_settings(load_config(config_path), store)

    def _sources_table_response(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "partials/sources_table_inner.html",
            page_context(
                request,
                "Sources",
                "sources",
                digests=_digests(),
                sources=sources.list_all(),
            ),
        )

    # ==================================================================
    # JSON API routes  (/api/...)
    # ==================================================================

    # --- Sources -------------------------------------------------------

    @router.get("/api/sources", response_model=None)
    async def api_list_sources() -> JSONResponse:
        return JSONResponse([dict(s) for s in sources.list_all()])

    @router.post("/api/sources", response_model=None)
    async def api_add_source(request: Request) -> JSONResponse:
        payload = await _read_source_payload(request)
        source_type = str(payload["source_type"])
        name = str(payload["name"])
        url = str(payload["url"])
        category = str(payload["category"])
        priority = int(payload["priority"])
        channel_id = str(payload["channel_id"])
        query = str(payload["query"])
        language = str(payload["language"])
        country = str(payload["country"])
        hn_feed = str(payload["hn_feed"])
        hn_max_items = int(payload["hn_max_items"])
        hn_min_score = int(payload["hn_min_score"])
        subreddit = str(payload["subreddit"])
        reddit_sort = str(payload["reddit_sort"])
        reddit_time_filter = str(payload["reddit_time_filter"])
        reddit_max_items = int(payload["reddit_max_items"])
        reddit_min_score = int(payload["reddit_min_score"])
        github_repo = str(payload["github_repo"])

        extra, feed_url, effective_type, conversion_note = _build_source_extra(
            source_type,
            url,
            channel_id,
            name,
            query=query,
            language=language,
            country=country,
            hn_feed=hn_feed,
            hn_max_items=hn_max_items,
            hn_min_score=hn_min_score,
            subreddit=subreddit,
            reddit_sort=reddit_sort,
            reddit_time_filter=reddit_time_filter,
            reddit_max_items=reddit_max_items,
            reddit_min_score=reddit_min_score,
            github_repo=github_repo,
        )
        sources.add(effective_type, name, category, priority, feed_url, extra=extra)
        resp: dict[str, Any] = {"ok": True}
        if conversion_note:
            resp["note"] = conversion_note
        return JSONResponse(resp)

    @router.put("/api/sources/{source_id}", response_model=None)
    async def api_update_source(source_id: int, request: Request) -> JSONResponse:
        payload = await _read_source_payload(request)
        error = _source_payload_error(payload)
        if error is not None:
            return JSONResponse({"error": error}, status_code=422)

        extra, feed_url, effective_type, conversion_note = _build_source_extra(
            str(payload["source_type"]),
            str(payload["url"]),
            str(payload["channel_id"]),
            str(payload["name"]),
            query=str(payload["query"]),
            language=str(payload["language"]),
            country=str(payload["country"]),
            hn_feed=str(payload["hn_feed"]),
            hn_max_items=int(payload["hn_max_items"]),
            hn_min_score=int(payload["hn_min_score"]),
            subreddit=str(payload["subreddit"]),
            reddit_sort=str(payload["reddit_sort"]),
            reddit_time_filter=str(payload["reddit_time_filter"]),
            reddit_max_items=int(payload["reddit_max_items"]),
            reddit_min_score=int(payload["reddit_min_score"]),
            github_repo=str(payload["github_repo"]),
        )
        sources.update(
            source_id,
            effective_type,
            str(payload["name"]),
            str(payload["category"]),
            int(payload["priority"]),
            feed_url,
            extra=extra,
        )
        resp: dict[str, Any] = {"ok": True}
        if conversion_note:
            resp["note"] = conversion_note
        return JSONResponse(resp)

    @router.delete("/api/sources/{source_id}", response_model=None)
    async def api_delete_source(source_id: int) -> JSONResponse:
        sources.delete(source_id)
        return JSONResponse({"ok": True})

    @router.patch("/api/sources/{source_id}/toggle", response_model=None)
    async def api_toggle_source(
        source_id: int, body: dict[str, Any]
    ) -> JSONResponse:
        """Enable or disable a source. Body: ``{"enabled": true|false}``."""
        if "enabled" not in body:
            return JSONResponse(
                {"error": "enabled field is required"}, status_code=422
            )
        sources.toggle(source_id, bool(body["enabled"]))
        return JSONResponse({"ok": True})

    @router.post("/api/sources/import-opml", response_model=None)
    async def api_import_opml(file: UploadFile = File(...)) -> JSONResponse:
        raw = await file.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            outline_rows = parse_opml_outlines(text)
        except Exception:
            return JSONResponse({"error": "Invalid OPML file."}, status_code=400)
        existing = {r["url"] for r in sources.list_all()}
        added = 0
        for row in outline_rows:
            xml_url = row["xmlUrl"]
            if xml_url in existing:
                continue
            title = row.get("title") or xml_url
            sources.add("rss", title[:240], "Imported", 2, xml_url)
            existing.add(xml_url)
            added += 1
        return JSONResponse({"added": added})

    @router.get("/api/sources/export.opml", response_class=PlainTextResponse)
    async def api_export_opml() -> PlainTextResponse:
        body = build_opml(sources.list_all())
        return PlainTextResponse(
            body,
            media_type="application/xml; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="condenseit-sources.opml"',
            },
        )

    # --- LLM config ----------------------------------------------------

    @router.get("/api/config/llm", response_model=None)
    async def api_get_llm() -> JSONResponse:
        merged = _merged()
        model = store.get_setting("model", merged.model)
        provider = store.get_setting("llm_provider", merged.llm.provider)
        ollama_reachable = False
        try:
            ollama_models = ollama_list_tags(merged.llm.ollama_host)
            ollama_reachable = True
        except Exception:
            ollama_models = []
        cheapest: str | None = None
        if merged.llm.openrouter_pick_cheapest:
            cheapest = pick_cheapest_text_model()

        return JSONResponse(
            {
                "provider": provider,
                "model": model,
                "openrouter_model": merged.llm.openrouter_model,
                "openrouter_pick_cheapest": merged.llm.openrouter_pick_cheapest,
                "cheapest_model_id": cheapest,
                "ollama_host": merged.llm.ollama_host,
                "ollama_models": ollama_models,
                "ollama_reachable": ollama_reachable,
            }
        )

    @router.put("/api/config/llm", response_model=None)
    async def api_save_llm(body: dict[str, Any]) -> JSONResponse:
        if "provider" in body:
            store.set_setting("llm_provider", str(body["provider"]))
        if "model" in body:
            store.set_setting("model", str(body["model"]))
        if "openrouter_model" in body and body["openrouter_model"]:
            store.set_setting("openrouter_model", str(body["openrouter_model"]))
        if "openrouter_pick_cheapest" in body:
            store.set_setting(
                "openrouter_pick_cheapest",
                "1" if body["openrouter_pick_cheapest"] else "0",
            )
        return JSONResponse({"ok": True})

    @router.post("/api/config/llm/ollama/pull", response_model=None)
    async def api_ollama_pull(body: dict[str, Any]) -> JSONResponse:
        merged = _merged()
        model = str(body.get("model", "")).strip()
        if not model:
            return JSONResponse({"error": "model required"}, status_code=422)
        try:
            ollama_pull(merged.llm.ollama_host, model)
            return JSONResponse({"message": f"Pulled {model}."})
        except Exception as exc:
            return JSONResponse({"message": f"Pull failed: {exc}"}, status_code=500)

    @router.post("/api/config/llm/ollama/delete", response_model=None)
    async def api_ollama_delete(body: dict[str, Any]) -> JSONResponse:
        merged = _merged()
        model = str(body.get("model", "")).strip()
        if not model:
            return JSONResponse({"error": "model required"}, status_code=422)
        try:
            ollama_delete(merged.llm.ollama_host, model)
            return JSONResponse({"message": f"Deleted {model}."})
        except Exception as exc:
            return JSONResponse({"message": f"Delete failed: {exc}"}, status_code=500)

    # --- API keys ------------------------------------------------------

    @router.get("/api/config/keys", response_model=None)
    async def api_list_keys() -> JSONResponse:
        return JSONResponse(
            [
                {"service": k["service"], "key_preview": k["key_preview"]}
                for k in keys.list_keys()
            ]
        )

    @router.post("/api/config/keys", response_model=None)
    async def api_save_key(body: dict[str, Any]) -> JSONResponse:
        service = str(body.get("service", "")).strip()
        key_value = str(body.get("key_value", "")).strip()
        if not service or not key_value:
            return JSONResponse(
                {"error": "service and key_value required"},
                status_code=422,
            )
        keys.store_key(service, key_value)
        return JSONResponse({"ok": True})

    @router.delete("/api/config/keys/{service}", response_model=None)
    async def api_delete_key(service: str) -> JSONResponse:
        keys.delete_key(service)
        return JSONResponse({"ok": True})

    # --- Digest pipeline settings -------------------------------------

    @router.get("/api/config/digest", response_model=None)
    async def api_get_digest_config() -> JSONResponse:
        merged = _merged()
        langs_raw = store.get_setting("preferred_languages", "")
        try:
            langs = json.loads(langs_raw) if langs_raw else merged.preferred_languages
        except Exception:
            langs = merged.preferred_languages
        kw_raw = store.get_setting("exclude_keywords", "")
        try:
            excl_kw = json.loads(kw_raw) if kw_raw else merged.exclude_keywords
        except Exception:
            excl_kw = merged.exclude_keywords
        return JSONResponse(
            {
                "max_articles_per_digest": merged.max_articles_per_digest,
                "balance_digest_categories": merged.balance_digest_categories,
                "max_articles_per_category": merged.max_articles_per_category,
                "max_article_age_hours": merged.max_article_age_hours,
                "preferred_languages": langs,
                "exclude_keywords": excl_kw,
                "max_key_takeaways": merged.max_key_takeaways,
                "max_summary_paragraphs": merged.max_summary_paragraphs,
            }
        )

    @router.put("/api/config/digest", response_model=None)
    async def api_save_digest_config(body: dict[str, Any]) -> JSONResponse:
        if "max_articles_per_digest" in body:
            try:
                val = int(body["max_articles_per_digest"])
                if 1 <= val <= 200:
                    store.set_setting("max_articles_per_digest", str(val))
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "max_articles_per_digest must be 1-200"},
                    status_code=422,
                )
        if "balance_digest_categories" in body:
            store.set_setting(
                "balance_digest_categories",
                "1" if body["balance_digest_categories"] else "0",
            )
        if "max_articles_per_category" in body:
            try:
                val = int(body["max_articles_per_category"])
                if 1 <= val <= 50:
                    store.set_setting("max_articles_per_category", str(val))
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "max_articles_per_category must be 1-50"},
                    status_code=422,
                )
        if "max_article_age_hours" in body:
            try:
                val = int(body["max_article_age_hours"])
                if val >= 0:
                    store.set_setting("max_article_age_hours", str(val))
                else:
                    return JSONResponse(
                        {"error": "max_article_age_hours must be 0 or greater"},
                        status_code=422,
                    )
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "max_article_age_hours must be 0 or greater"},
                    status_code=422,
                )
        if "preferred_languages" in body:
            langs = body["preferred_languages"]
            if not isinstance(langs, list):
                return JSONResponse(
                    {"error": "preferred_languages must be a list"},
                    status_code=422,
                )
            cleaned = [
                str(language).strip().lower()
                for language in langs
                if str(language).strip()
            ]
            store.set_setting("preferred_languages", json.dumps(cleaned))
        if "exclude_keywords" in body:
            kw_list = body["exclude_keywords"]
            if not isinstance(kw_list, list):
                return JSONResponse(
                    {"error": "exclude_keywords must be a list"},
                    status_code=422,
                )
            cleaned_kw = [
                str(phrase).strip()
                for phrase in kw_list
                if str(phrase).strip()
            ]
            store.set_setting("exclude_keywords", json.dumps(cleaned_kw))
        if "max_key_takeaways" in body:
            try:
                val = int(body["max_key_takeaways"])
                if 1 <= val <= 10:
                    store.set_setting("max_key_takeaways", str(val))
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "max_key_takeaways must be 1-10"},
                    status_code=422,
                )
        if "max_summary_paragraphs" in body:
            try:
                val = int(body["max_summary_paragraphs"])
                if 1 <= val <= 10:
                    store.set_setting("max_summary_paragraphs", str(val))
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "max_summary_paragraphs must be 1-10"},
                    status_code=422,
                )
        return JSONResponse({"ok": True})

    # --- Budget limits -------------------------------------------------

    @router.get("/api/config/budget-limits", response_model=None)
    async def api_get_budget_limits() -> JSONResponse:
        merged = _merged()
        return JSONResponse(
            {
                "daily_budget_usd": merged.llm.openrouter_daily_budget_usd,
                "monthly_budget_usd": merged.llm.openrouter_monthly_budget_usd,
            }
        )

    @router.put("/api/config/budget-limits", response_model=None)
    async def api_save_budget_limits(body: dict[str, Any]) -> JSONResponse:
        if "daily_budget_usd" in body:
            try:
                val = float(body["daily_budget_usd"])
                if val < 0:
                    raise ValueError
                store.set_setting("openrouter_daily_budget_usd", str(val))
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "daily_budget_usd must be a non-negative number"},
                    status_code=422,
                )
        if "monthly_budget_usd" in body:
            try:
                val = float(body["monthly_budget_usd"])
                if val < 0:
                    raise ValueError
                store.set_setting("openrouter_monthly_budget_usd", str(val))
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "monthly_budget_usd must be a non-negative number"},
                    status_code=422,
                )
        return JSONResponse({"ok": True})

    # --- Password management -------------------------------------------

    @router.get("/api/config/password-info", response_model=None)
    async def api_password_info() -> JSONResponse:
        """Return the current password source so the UI can show a warning."""
        db_pw = store.get_setting("auth_password", "")
        if db_pw:
            source = "db"
        else:
            env_pw = (
                os.environ.get("CONDENSEIT_AUTH_PASSWORD", "").strip()
                or os.environ.get("DIGEST_PWA_AUTH_PASSWORD", "").strip()
            )
            source = "env" if env_pw else "default"
        return JSONResponse({"source": source, "using_default": source == "default"})

    @router.put("/api/config/password", response_model=None)
    async def api_change_password(body: dict[str, Any]) -> JSONResponse:
        """Change the admin password. Stores the new password in the DB."""
        current = str(body.get("current_password", "")).strip()
        new_pw = str(body.get("new_password", "")).strip()

        if not current or not new_pw:
            return JSONResponse(
                {"error": "current_password and new_password are required"},
                status_code=422,
            )
        if len(new_pw) < 8:
            return JSONResponse(
                {"error": "New password must be at least 8 characters."},
                status_code=422,
            )

        db_pw = store.get_setting("auth_password", "")
        env_pw = (
            os.environ.get("CONDENSEIT_AUTH_PASSWORD", "").strip()
            or os.environ.get("DIGEST_PWA_AUTH_PASSWORD", "").strip()
        )
        effective = db_pw or env_pw or "condenseit"

        if not secrets.compare_digest(current, effective):
            return JSONResponse(
                {"error": "Current password is incorrect."},
                status_code=401,
            )

        store.set_setting("auth_password", new_pw)
        return JSONResponse({"ok": True})

    # --- Run logs ------------------------------------------------------

    @router.get("/api/logs", response_model=None)
    async def api_list_logs() -> JSONResponse:
        rows = store.list_run_logs(limit=30)
        return JSONResponse([dict(r) for r in rows])

    @router.get("/api/logs/latest", response_model=None)
    async def api_latest_log() -> JSONResponse:
        row = store.latest_run_log()
        if not row:
            return JSONResponse(None)
        return JSONResponse(dict(row))

    @router.get("/api/logs/{log_id}", response_model=None)
    async def api_get_log(log_id: int) -> JSONResponse:
        row = store.get_run_log(log_id)
        if not row:
            return JSONResponse(None, status_code=404)
        return JSONResponse(dict(row))

    # ==================================================================
    # Legacy Jinja2 HTML routes (/admin/...)
    # ==================================================================

    @router.get("/admin/", response_model=None)
    async def admin_home() -> RedirectResponse:
        return RedirectResponse("/admin/sources", status_code=303)

    @router.get("/admin/sources", response_class=HTMLResponse)
    async def sources_list(request: Request) -> HTMLResponse:
        if _is_htmx(request):
            return _sources_table_response(request)
        return templates.TemplateResponse(
            request,
            "sources.html",
            page_context(
                request,
                "Sources",
                "sources",
                digests=_digests(),
                sources=sources.list_all(),
            ),
        )

    @router.get("/admin/sources/table", response_class=HTMLResponse)
    async def sources_table(request: Request) -> HTMLResponse:
        return _sources_table_response(request)

    @router.post("/admin/sources", response_model=None)
    async def sources_add(
        request: Request,
        source_type: str = Form(...),
        name: str = Form(...),
        url: str = Form(""),
        category: str = Form("General"),
        priority: int = Form(2),
        channel_id: str = Form(""),
        query: str = Form(""),
        language: str = Form("en"),
        country: str = Form("US"),
        hn_feed: str = Form("top"),
        hn_max_items: int = Form(20),
        hn_min_score: int = Form(50),
        subreddit: str = Form(""),
        reddit_sort: str = Form("hot"),
        reddit_time_filter: str = Form("day"),
        reddit_max_items: int = Form(20),
        reddit_min_score: int = Form(10),
        github_repo: str = Form(""),
    ) -> HTMLResponse | RedirectResponse:
        extra, feed_url, effective_type, _note = _build_source_extra(
            source_type,
            url,
            channel_id,
            name,
            query=query,
            language=language,
            country=country,
            hn_feed=hn_feed,
            hn_max_items=hn_max_items,
            hn_min_score=hn_min_score,
            subreddit=subreddit,
            reddit_sort=reddit_sort,
            reddit_time_filter=reddit_time_filter,
            reddit_max_items=reddit_max_items,
            reddit_min_score=reddit_min_score,
            github_repo=github_repo,
        )
        sources.add(effective_type, name, category, priority, feed_url, extra=extra)
        if _is_htmx(request):
            return _sources_table_response(request)
        return RedirectResponse("/admin/sources", status_code=303)

    @router.post("/admin/sources/{source_id}/delete", response_model=None)
    async def sources_delete(
        request: Request,
        source_id: int,
    ) -> HTMLResponse | RedirectResponse:
        sources.delete(source_id)
        if _is_htmx(request):
            return _sources_table_response(request)
        return RedirectResponse("/admin/sources", status_code=303)

    @router.post("/admin/sources/import-opml", response_model=None)
    async def sources_import_opml(
        request: Request,
        file: UploadFile = File(...),
    ) -> HTMLResponse | RedirectResponse:
        raw = await file.read()
        text = raw.decode("utf-8", errors="replace")
        try:
            outline_rows = parse_opml_outlines(text)
        except Exception:
            if _is_htmx(request):
                return HTMLResponse(
                    '<p class="flash flash-warn">Invalid OPML file.</p>',
                    status_code=400,
                )
            return RedirectResponse("/admin/sources?imported=0&err=1", status_code=303)
        existing = {r["url"] for r in sources.list_all()}
        added = 0
        for row in outline_rows:
            xml_url = row["xmlUrl"]
            if xml_url in existing:
                continue
            title = row.get("title") or xml_url
            sources.add("rss", title[:240], "Imported", 2, xml_url)
            existing.add(xml_url)
            added += 1
        if _is_htmx(request):
            return _sources_table_response(request)
        return RedirectResponse(
            f"/admin/sources?imported={added}",
            status_code=303,
        )

    @router.get("/admin/sources/export.opml", response_class=PlainTextResponse)
    async def sources_export_opml() -> PlainTextResponse:
        body = build_opml(sources.list_all())
        return PlainTextResponse(
            body,
            media_type="application/xml; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="condenseit-sources.opml"',
            },
        )

    @router.get("/admin/llm", response_class=HTMLResponse)
    async def llm_config(request: Request) -> HTMLResponse:
        merged = _merged()
        model = store.get_setting("model", merged.model)
        provider = store.get_setting("llm_provider", merged.llm.provider)
        try:
            ollama_models = ollama_list_tags(merged.llm.ollama_host)
        except Exception:
            ollama_models = []
        return templates.TemplateResponse(
            request,
            "llm_config.html",
            page_context(
                request,
                "LLM",
                "llm",
                digests=_digests(),
                model=model,
                provider=provider,
                ollama_host=merged.llm.ollama_host,
                or_model=merged.llm.openrouter_model,
                openrouter_pick_cheapest=merged.llm.openrouter_pick_cheapest,
                ollama_models=ollama_models,
                msg=request.query_params.get("msg", ""),
            ),
        )

    @router.post("/admin/llm")
    async def llm_save(
        provider: str = Form(...),
        model: str = Form(...),
        openrouter_model: str = Form(""),
        openrouter_pick_cheapest: str = Form(""),
    ) -> RedirectResponse:
        store.set_setting("llm_provider", provider)
        store.set_setting("model", model)
        if openrouter_model:
            store.set_setting("openrouter_model", openrouter_model)
        store.set_setting(
            "openrouter_pick_cheapest",
            "1" if openrouter_pick_cheapest == "on" else "0",
        )
        return RedirectResponse("/admin/llm", status_code=303)

    @router.post("/admin/llm/ollama/pull", response_model=None)
    async def llm_ollama_pull(
        request: Request,
        pull_model: str = Form(...),
    ) -> HTMLResponse | RedirectResponse:
        merged = _merged()
        try:
            ollama_pull(merged.llm.ollama_host, pull_model)
            msg = f"Pulled {pull_model}."
        except Exception as exc:
            msg = f"Pull failed: {exc}"
        if _is_htmx(request):
            return HTMLResponse(f'<p class="flash">{msg}</p>')
        return RedirectResponse(f"/admin/llm?msg={quote(msg[:500])}", status_code=303)

    @router.post("/admin/llm/ollama/delete", response_model=None)
    async def llm_ollama_delete(
        request: Request,
        delete_model: str = Form(...),
    ) -> HTMLResponse | RedirectResponse:
        merged = _merged()
        try:
            ollama_delete(merged.llm.ollama_host, delete_model)
            msg = f"Deleted {delete_model}."
        except Exception as exc:
            msg = f"Delete failed: {exc}"
        if _is_htmx(request):
            return HTMLResponse(f'<p class="flash flash-warn">{msg}</p>')
        return RedirectResponse(f"/admin/llm?msg={quote(msg[:500])}", status_code=303)

    @router.get("/admin/keys", response_class=HTMLResponse)
    async def keys_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "keys.html",
            page_context(
                request,
                "API Keys",
                "keys",
                digests=_digests(),
                keys=keys.list_keys(),
            ),
        )

    @router.post("/admin/keys")
    async def keys_save(
        service: str = Form(...),
        key_value: str = Form(...),
    ) -> RedirectResponse:
        keys.store_key(service, key_value)
        return RedirectResponse("/admin/keys", status_code=303)

    @router.post("/admin/keys/{service}/delete")
    async def keys_delete(service: str) -> RedirectResponse:
        keys.delete_key(service)
        return RedirectResponse("/admin/keys", status_code=303)

    return router
