"""FastAPI application: digest, ratings, admin."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import markdown
from fastapi import FastAPI, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles

from condenseit.config import load_config
from condenseit.learning.preference_engine import PreferenceEngine
from condenseit.settings_overlay import apply_db_settings
from condenseit.store.database import ContentStore
from condenseit.web.admin.routes import create_admin_router
from condenseit.web.digest_job import DigestJobManager
from condenseit.web.templating import page_context, templates

_STATIC = Path(__file__).resolve().parent / "static"


def _frontend_dist_dir() -> Path:
    """Resolve the Vite ``dist`` folder for the SPA shell.

    - ``CONDENSEIT_FRONTEND_DIST``: explicit path (set in Docker Compose).
    - Repo checkout: ``src/condenseit/web`` -> four parents -> repo
      ``frontend/dist``.
    - Else ``./frontend/dist`` from the process cwd (e.g. Docker ``WORKDIR``).
    """
    override = (os.environ.get("CONDENSEIT_FRONTEND_DIST") or "").strip()
    if override:
        return Path(override)
    here = Path(__file__).resolve().parent
    legacy = here.parent.parent.parent.parent / "frontend" / "dist"
    if legacy.is_dir():
        return legacy
    cwd_candidate = Path.cwd() / "frontend" / "dist"
    if cwd_candidate.is_dir():
        return cwd_candidate
    return legacy

# ---------------------------------------------------------------------------
# Summary cleaning: strip LLM prompt artifacts from stored summaries
# ---------------------------------------------------------------------------
_SUMMARY_PREFIX = re.compile(
    r"^(?:here\s+is\s+(?:a\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?"
    r"(?:brief\s+)?summary[^:]*:|this\s+(?:is\s+(?:a|an)\s+)?"
    r"(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:)\s*",
    re.IGNORECASE,
)
_NOTE_SUFFIX = re.compile(r"\n+\s*note:\s.*$", re.IGNORECASE | re.DOTALL)


def _clean_summary(raw: str) -> str:
    """Remove common LLM preamble/postamble from summary text."""
    s = (raw or "").strip()
    s = _SUMMARY_PREFIX.sub("", s)
    s = _NOTE_SUFFIX.sub("", s)
    return s.strip()


def _clean_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a new list with summaries cleaned."""
    out = []
    for it in items:
        row = dict(it)
        if "summary" in row:
            row["summary"] = _clean_summary(str(row.get("summary") or ""))
        out.append(row)
    return out


def create_app(config_path: str | None = None) -> FastAPI:
    config = load_config(config_path)
    store = ContentStore()
    config = apply_db_settings(config, store)
    job_manager = DigestJobManager(config_path)
    spa_dist = _frontend_dist_dir()
    relevance = config.relevance
    preferences = PreferenceEngine(
        store,
        relevance.min_ratings_for_learning,
        relevance.tfidf_preference_weight,
        relevance.category_preference_weight,
        relevance.source_preference_weight,
        relevance.rating_decay_half_life_days,
    )

    app = FastAPI(title="CondenseIt", docs_url="/docs")
    app.state.job_manager = job_manager
    templates.env.globals["digest_job"] = job_manager.snapshot

    # ------------------------------------------------------------------
    # Static assets (legacy CSS/JS for Jinja2 pages)
    # ------------------------------------------------------------------
    if _STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

    app.include_router(create_admin_router(config_path, store))

    # ==================================================================
    # JSON API routes
    # ==================================================================

    # --- Digest list / detail -----------------------------------------

    @app.get("/api/digests", response_model=None)
    async def api_list_digests() -> JSONResponse:
        rows = store.list_digests(limit=20)
        return JSONResponse(
            [{"id": r["id"], "created_at": r.get("created_at", "")} for r in rows]
        )

    @app.get("/api/digests/latest", response_model=None)
    async def api_latest_digest() -> JSONResponse:
        row = store.latest_digest()
        if not row:
            return JSONResponse(None)
        return JSONResponse(_build_digest_detail(row, store))

    @app.get("/api/digests/{digest_id}", response_model=None)
    async def api_get_digest(digest_id: int) -> JSONResponse:
        rows = list(
            store.db.query("SELECT * FROM digests WHERE id = ?", [digest_id])
        )
        if not rows:
            return JSONResponse(None, status_code=404)
        return JSONResponse(_build_digest_detail(dict(rows[0]), store))

    # --- Job status / control (already existed, kept as-is) -----------

    @app.get("/api/digest/status")
    async def api_digest_status() -> dict[str, Any]:
        return job_manager.snapshot()

    @app.post("/api/digest/run")
    async def api_digest_run(
        dry_run: int = Query(0),
        skip_email: int = Query(0),
        skip_deploy: int = Query(0),
    ) -> JSONResponse:
        ok, message = job_manager.start(
            dry_run=bool(dry_run),
            skip_email=bool(skip_email),
            skip_deploy=bool(skip_deploy),
        )
        status = 200 if ok else 409
        payload = {"ok": ok, "message": message, "job": job_manager.snapshot()}
        return JSONResponse(payload, status_code=status)

    @app.post("/api/digest/dismiss")
    async def api_digest_dismiss() -> dict[str, Any]:
        job_manager.dismiss()
        return job_manager.snapshot()

    # --- Ratings -------------------------------------------------------

    @app.get("/api/ratings", response_model=None)
    async def api_ratings() -> JSONResponse:
        articles = _rate_page_article_rows(store, limit=50)
        return JSONResponse(articles)

    @app.post("/api/ratings", response_model=None)
    async def api_rate(body: dict[str, Any]) -> JSONResponse:
        url = str(body.get("url", "")).strip()
        rating = int(body.get("rating", 0))
        if not url or not 1 <= rating <= 5:
            return JSONResponse({"error": "Invalid url or rating"}, status_code=422)
        store.rate_article(url, rating)
        return JSONResponse({"ok": True})

    @app.get("/api/ratings/export", response_model=None)
    async def api_ratings_export() -> JSONResponse:
        """Export all ratings as {ratings:[{url,rating}]} for ratings_import_url.

        Compatible with ``condenseit ratings-import --url`` and the
        ``CONDENSEIT_RATINGS_IMPORT_URL`` / ``digest_pwa.ratings_import_url``
        settings so the local pipeline can pull remote ratings automatically
        before each digest run.
        """
        if "ratings" not in store.db.table_names():
            return JSONResponse({"ratings": []})
        rows = list(
            store.db.query(
                "SELECT url, rating FROM ratings"
                " WHERE rating >= 1 AND rating <= 5"
                " ORDER BY rated_at DESC",
            ),
        )
        payload = [
            {"url": str(r["url"]), "rating": int(r["rating"])} for r in rows
        ]
        return JSONResponse({"ratings": payload})

    # --- Read tracking -------------------------------------------------

    @app.get("/api/read", response_model=None)
    async def api_get_read() -> JSONResponse:
        """Return all URLs the user has marked as read."""
        urls = sorted(store.get_read_urls())
        return JSONResponse({"urls": urls})

    @app.post("/api/read", response_model=None)
    async def api_mark_read(body: dict[str, Any]) -> JSONResponse:
        """Mark or unmark a single article URL as read.

        Body: ``{"url": "...", "read": true}``
        When ``read`` is ``false`` the URL is removed from the read set so the
        article becomes eligible to appear in the next digest again.
        """
        url = str(body.get("url", "")).strip()
        is_read = bool(body.get("read", True))
        if not url:
            return JSONResponse({"error": "Missing url"}, status_code=422)
        if is_read:
            store.mark_article_read(url)
        else:
            store.mark_article_unread(url)
        return JSONResponse({"ok": True})

    @app.get("/api/read/export", response_model=None)
    async def api_read_export() -> JSONResponse:
        """Export all read URLs as ``{"urls": [...]}`` for CONDENSEIT_READ_IMPORT_URL.

        Compatible with ``digest_pwa.read_import_url`` and the
        ``CONDENSEIT_READ_IMPORT_URL`` env var so the local pipeline can pull
        remote read state automatically before each digest run.
        """
        urls = sorted(store.get_read_urls())
        return JSONResponse({"urls": urls})

    # --- Preference profile --------------------------------------------

    @app.get("/api/preferences/profile", response_model=None)
    async def api_preferences_profile() -> JSONResponse:
        """Return a snapshot of the learned preference profile.

        Shows liked/disliked terms, category scores, source scores, and
        rating counts so the user can verify what the engine has learned.
        """
        return JSONResponse(preferences.profile_summary())

    # --- Admin overview -----------------------------------------------

    @app.get("/api/admin/overview", response_model=None)
    async def api_admin_overview() -> JSONResponse:
        from condenseit.store.sources import SourceRegistry

        merged = apply_db_settings(load_config(config_path), store)
        sources = SourceRegistry(store)
        sources.seed_from_config(merged)
        latest = store.latest_digest()
        return JSONResponse(
            {
                "source_count": len(sources.list_all()),
                "provider": merged.llm.provider,
                "model": store.get_setting("model", merged.model),
                "latest": (
                    {"id": latest["id"], "created_at": latest.get("created_at", "")}
                    if latest
                    else None
                ),
            }
        )

    # ==================================================================
    # Legacy Jinja2 HTML routes (kept during transition)
    # ==================================================================

    def _digest_list() -> list[dict[str, Any]]:
        return store.list_digests(limit=12)

    @app.get("/", response_class=HTMLResponse, response_model=None)
    async def home(
        request: Request,
        id: int | None = Query(None, alias="id"),
        raw: int = Query(0),
    ) -> Response:
        row, html, meta, digest_items = _load_digest(id, store)
        if raw and row:
            return PlainTextResponse(row.get("markdown", ""), media_type="text/plain")

        selected_id = row.get("id") if row else None

        # Serve SPA if the dist is present; else fall back to Jinja2
        if spa_dist.is_dir() and not raw:
            from starlette.responses import FileResponse

            return FileResponse(spa_dist / "index.html")

        return templates.TemplateResponse(
            request,
            "digest.html",
            page_context(
                request,
                "Digest",
                "digest",
                digests=_digest_list(),
                selected_id=selected_id,
                digest_html=html if html else None,
                digest_items=digest_items,
                meta=meta if meta else None,
            ),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # SPA catch-all: serve index.html for all other GET requests
    # ------------------------------------------------------------------
    if spa_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(spa_dist), html=True),
            name="spa",
        )

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_digest_detail(
    row: dict[str, Any],
    store: ContentStore | None = None,
) -> dict[str, Any]:
    """Convert a DB digest row to the JSON API response shape.

    When ``store`` is supplied, saved star ratings are merged into each item
    so the frontend can show the user's current rating alongside each card.
    """
    md = row.get("markdown") or ""
    html = markdown.markdown(md, extensions=["tables", "fenced_code"])
    meta = _parse_stats(row.get("stats_json", ""))
    raw_items = meta.pop("digest_items", None)
    items: list[dict[str, Any]] = (
        raw_items if isinstance(raw_items, list) else []
    )
    meta["created_at"] = row.get("created_at", "")
    meta["id"] = row.get("id")
    cleaned = _clean_items(items)
    if store is not None:
        cleaned = _attach_ratings(store, cleaned)
    return {
        "meta": meta,
        "html": html,
        "items": cleaned,
    }


def _parse_stats(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _load_digest(
    digest_id: int | None,
    store: ContentStore,
) -> tuple[dict[str, Any] | None, str, dict[str, Any], list[dict[str, Any]]]:
    row: dict[str, Any] | None
    if digest_id is not None:
        rows = list(
            store.db.query("SELECT * FROM digests WHERE id = ?", [digest_id])
        )
        row = dict(rows[0]) if rows else None
    else:
        row = store.latest_digest()

    if not row:
        return None, "", {}, []

    md = row.get("markdown") or ""
    html = markdown.markdown(md, extensions=["tables", "fenced_code"])
    meta = _parse_stats(row.get("stats_json", ""))
    raw_items = meta.pop("digest_items", None)
    digest_items: list[dict[str, Any]] = (
        raw_items if isinstance(raw_items, list) else []
    )
    meta["created_at"] = row.get("created_at", "")
    meta["id"] = row.get("id")
    return row, html, meta, digest_items


def _attach_ratings(
    store: ContentStore,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge rating from ratings table into article rows (mutates in place)."""
    urls = [str(r["url"]) for r in rows if r.get("url")]
    if not urls:
        return rows
    placeholders = ", ".join(["?"] * len(urls))
    q = f"SELECT url, rating FROM ratings WHERE url IN ({placeholders})"
    by_url = {
        str(row["url"]): row["rating"]
        for row in store.db.query(q, urls)
    }
    for r in rows:
        u = str(r.get("url", ""))
        r["rating"] = by_url.get(u)
    return rows


def _rate_page_article_rows(
    store: ContentStore,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Prefer URLs from recent digest stats; fall back to articles table."""
    rows_out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in store.list_digests(limit=30):
        stats_raw = d.get("stats_json", "") or ""
        meta = _parse_stats(stats_raw)
        items = meta.get("digest_items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            title = str(item.get("title", "") or "").strip() or url
            cat_raw = str(item.get("category", "") or "").strip()
            rows_out.append(
                {
                    "url": url,
                    "title": title,
                    "category": cat_raw or "General",
                }
            )
            if len(rows_out) >= limit:
                break
        if len(rows_out) >= limit:
            break
    if rows_out:
        return _attach_ratings(store, rows_out)
    legacy = list(
        store.db.query(
            """
            SELECT a.url, a.title, a.category, r.rating
            FROM articles a
            LEFT JOIN ratings r ON r.url = a.url
            ORDER BY a.collected_at DESC
            LIMIT ?
            """,
            [limit],
        )
    )
    return [dict(r) for r in legacy]
