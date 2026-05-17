"""FastAPI application: digest, ratings, admin."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import markdown
from fastapi import FastAPI, Query, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from condenseit.config import load_config
from condenseit.learning.preference_engine import PreferenceEngine
from condenseit.providers.base import parse_summary_response
from condenseit.settings_overlay import apply_db_settings
from condenseit.store.database import ContentStore
from condenseit.web.admin.routes import create_admin_router
from condenseit.web.digest_job import DigestJobManager
from condenseit.web.scheduler import (
    _SCHEDULER_STATE,
    get_scheduler_status,
    is_env_scheduler_enabled,
    scheduler_loop,
    trigger_reschedule,
)
from condenseit.web.templating import page_context, templates

_STATIC = Path(__file__).resolve().parent / "static"
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def _frontend_dist_dir() -> Path:
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


_SUMMARY_PREFIX = re.compile(
    r"^(?:here\s+is\s+(?:a\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?"
    r"(?:brief\s+)?summary[^:]*:|this\s+(?:is\s+(?:a|an)\s+)?"
    r"(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:)\s*",
    re.IGNORECASE,
)
_NOTE_SUFFIX = re.compile(r"\n+\s*note:\s.*$", re.IGNORECASE | re.DOTALL)


def _clean_summary(raw: str) -> str:
    s = (raw or "").strip()
    s = _SUMMARY_PREFIX.sub("", s)
    s = _NOTE_SUFFIX.sub("", s)
    return s.strip()


def _normalize_item(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    if not (row.get("tldr") or row.get("key_takeaways")):
        parsed = parse_summary_response(str(row.get("summary") or ""))
        row["tldr"] = parsed["tldr"]
        row["key_takeaways"] = parsed["key_takeaways"]
        row["summary"] = parsed["summary"]
    elif str(row.get("summary") or "").strip().startswith("{"):
        # Structured fields are already populated but the summary column still
        # holds the raw JSON blob from the old storage format.  Extract just
        # the prose text so the UI never renders raw JSON.
        parsed = parse_summary_response(str(row["summary"]))
        row["summary"] = parsed["summary"] or parsed["tldr"] or row["summary"]
    row["summary"] = _clean_summary(str(row.get("summary") or ""))
    if row.get("tldr"):
        row["tldr"] = _clean_summary(str(row["tldr"]))
    if not isinstance(row.get("key_takeaways"), list):
        row["key_takeaways"] = []
    return row


def _clean_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_item(it) for it in items]


def create_app(config_path: str | None = None) -> FastAPI:
    # Ensure condenseit.* loggers are visible at INFO when started via uvicorn
    # directly (e.g. systemd). The CLI calls basicConfig(INFO) itself; this is
    # a no-op there because the condenseit logger would already propagate to the
    # INFO-level root logger. Without this, _ListHandler in DigestJobManager
    # captures nothing and /admin/logs stays empty.
    logging.getLogger("condenseit").setLevel(logging.INFO)

    config = load_config(config_path)
    store = ContentStore()
    config = apply_db_settings(config, store)
    job_manager = DigestJobManager(config_path, store=store)
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

    def _get_schedule_times() -> list[str]:
        """Return current schedule times from DB, falling back to config."""
        raw = store.get_setting("schedule_times", "")
        if raw:
            try:
                times = json.loads(raw)
                if isinstance(times, list):
                    return [str(t) for t in times]
            except Exception:
                pass
        return config.schedule.get("times", [])

    def _is_scheduler_enabled() -> bool:
        """Check DB setting first, then fall back to env var."""
        db_val = store.get_setting("scheduler_enabled", "")
        if db_val == "1":
            return True
        if db_val == "0":
            return False
        return is_env_scheduler_enabled()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Always start the scheduler task; the loop checks _is_scheduler_enabled()
        # on each iteration so it can be toggled live from the admin UI.
        _SCHEDULER_STATE["schedule_times"] = _get_schedule_times()
        task = asyncio.create_task(
            scheduler_loop(
                _get_schedule_times,
                job_manager.start,
                is_enabled=_is_scheduler_enabled,
            ),
            name="condenseit-scheduler",
        )
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="CondenseIt", docs_url="/docs", lifespan=lifespan)
    app.state.job_manager = job_manager
    templates.env.globals["digest_job"] = job_manager.snapshot

    default_auth_password = "condenseit"
    _env_auth_password = (
        os.environ.get("CONDENSEIT_AUTH_PASSWORD", "").strip()
        or os.environ.get("DIGEST_PWA_AUTH_PASSWORD", "").strip()
    )
    _session_secret = os.environ.get("DIGEST_PWA_SESSION_SECRET", "").strip()

    if not _session_secret:
        logging.warning(
            "DIGEST_PWA_SESSION_SECRET is not set; a temporary random key "
            "will be used. All sessions will be invalidated on every service "
            "restart. Set DIGEST_PWA_SESSION_SECRET=<openssl rand -hex 32> "
            "in .env to persist sessions across restarts."
        )
        _session_secret = secrets.token_hex(32)

    def _get_auth_password() -> str:
        """Effective password: DB > env var > built-in default."""
        db_pw = store.get_setting("auth_password", "")
        if db_pw:
            return db_pw
        return _env_auth_password if _env_auth_password else default_auth_password

    def _password_source() -> str:
        if store.get_setting("auth_password", ""):
            return "db"
        if _env_auth_password:
            return "env"
        return "default"

    @app.get("/api/auth/check", response_model=None)
    async def api_auth_check(request: Request) -> JSONResponse:
        session: dict[str, Any] = getattr(request, "session", {})
        if session.get("authenticated"):
            return JSONResponse({"authenticated": True})
        return JSONResponse({"authenticated": False}, status_code=401)

    @app.post("/api/auth/login", response_model=None)
    async def api_auth_login(
        request: Request,
        body: dict[str, Any],
    ) -> JSONResponse:
        pw = str(body.get("password", "")).strip()
        if not pw or not secrets.compare_digest(pw, _get_auth_password()):
            return JSONResponse({"error": "Invalid password"}, status_code=401)
        request.session["authenticated"] = True
        return JSONResponse({"ok": True})

    @app.post("/api/auth/logout", response_model=None)
    async def api_auth_logout(request: Request) -> JSONResponse:
        session: dict[str, Any] = getattr(request, "session", {})
        session.clear()
        return JSONResponse({"ok": True})

    @app.middleware("http")
    async def _auth_guard(
        request: Request,
        call_next: Callable,
    ) -> Response:
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/auth/"):
            effective_pw = _get_auth_password()
            auth_header = request.headers.get("Authorization", "")
            bearer_ok = auth_header.startswith("Bearer ") and secrets.compare_digest(
                auth_header[len("Bearer "):].strip(),
                effective_pw,
            )
            session: dict[str, Any] = getattr(request, "session", {})
            if not bearer_ok and not session.get("authenticated"):
                return JSONResponse(
                    {"detail": "Not authenticated"},
                    status_code=401,
                )
        return await call_next(request)

    _https_only = os.environ.get("CONDENSEIT_HTTPS_ONLY", "").strip()
    https_only = _https_only == "1" if _https_only else False
    app.add_middleware(
        SessionMiddleware,
        secret_key=_session_secret,
        max_age=7_776_000,
        https_only=https_only,
        same_site="lax",
    )

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

    # --- Job status / control -----------------------------------------

    @app.get("/api/digest/status")
    async def api_digest_status() -> dict[str, Any]:
        return job_manager.snapshot()

    @app.post("/api/digest/run")
    async def api_digest_run(
        dry_run: int = Query(0),
        skip_deploy: int = Query(0),
    ) -> JSONResponse:
        ok, message = job_manager.start(
            dry_run=bool(dry_run),
            skip_deploy=bool(skip_deploy),
        )
        status = 200 if ok else 409
        payload = {"ok": ok, "message": message, "job": job_manager.snapshot()}
        return JSONResponse(payload, status_code=status)

    @app.post("/api/digest/dismiss")
    async def api_digest_dismiss() -> dict[str, Any]:
        job_manager.dismiss()
        return job_manager.snapshot()

    # --- Scheduler status / config ------------------------------------

    @app.get("/api/scheduler/status", response_model=None)
    async def api_scheduler_status() -> JSONResponse:
        return JSONResponse(get_scheduler_status())

    @app.get("/api/config/schedule", response_model=None)
    async def api_get_schedule() -> JSONResponse:
        times = _get_schedule_times()
        return JSONResponse(
            {
                "times": times,
                "enabled": _is_scheduler_enabled(),
                "next_run_utc": _SCHEDULER_STATE.get("next_run_utc"),
            }
        )

    @app.put("/api/config/schedule", response_model=None)
    async def api_save_schedule(body: dict[str, Any]) -> JSONResponse:
        # Handle enabled toggle
        if "enabled" in body:
            store.set_setting(
                "scheduler_enabled",
                "1" if body["enabled"] else "0",
            )

        # Handle times update
        if "times" in body:
            times = body["times"]
            if not isinstance(times, list):
                return JSONResponse({"error": "times must be a list"}, status_code=422)
            validated: list[str] = []
            for t in times:
                t = str(t).strip()
                if _TIME_RE.match(t):
                    validated.append(t)
                else:
                    return JSONResponse(
                        {"error": f"Invalid time format: {t!r}. Use HH:MM (24-hour)."},
                        status_code=422,
                    )
            store.set_setting("schedule_times", json.dumps(validated))
            _SCHEDULER_STATE["schedule_times"] = validated

        # Wake the scheduler loop so changes take effect immediately.
        await trigger_reschedule()
        return JSONResponse({"ok": True})

    # --- Budget -------------------------------------------------------

    @app.get("/api/config/budget", response_model=None)
    async def api_budget() -> JSONResponse:
        merged = apply_db_settings(load_config(config_path), store)
        or_key = merged.llm.openrouter_api_key
        if not or_key:
            from condenseit.store.secure_keys import SecureKeyStore
            or_key = SecureKeyStore(store).get_key("openrouter") or ""

        openrouter_data: dict[str, Any] | None = None
        if or_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://openrouter.ai/api/v1/key",
                        headers={"Authorization": f"Bearer {or_key}"},
                    )
                    resp.raise_for_status()
                    payload = resp.json()
                    data = payload.get("data", {})
                    openrouter_data = {
                        "usage_daily": float(data.get("usage_daily") or 0),
                        "usage_weekly": float(data.get("usage_weekly") or 0),
                        "usage_monthly": float(data.get("usage_monthly") or 0),
                        "limit": data.get("limit"),
                        "limit_remaining": data.get("limit_remaining"),
                        "is_free_tier": bool(data.get("is_free_tier", True)),
                    }
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "OpenRouter key stats failed: %s", exc
                )

        today_str = _today_iso()
        month_str = today_str[:7]

        today_usd = _sum_spending(store, f"recorded_at >= '{today_str}'")
        month_usd = _sum_spending(store, f"recorded_at >= '{month_str}-01'")

        by_model: list[dict[str, Any]] = []
        if "spending" in store.db.table_names():
            rows = list(store.db.query(
                "SELECT model, SUM(amount_usd) as total_usd, COUNT(*) as requests"
                " FROM spending GROUP BY model ORDER BY total_usd DESC"
            ))
            by_model = [
                {
                    "model": str(r["model"] or ""),
                    "total_usd": float(r["total_usd"] or 0),
                    "requests": int(r["requests"] or 0),
                }
                for r in rows
            ]

        recent_digests: list[dict[str, Any]] = []
        for digest in store.list_digests(limit=10):
            d_id = digest.get("id")
            d_at = str(digest.get("created_at", ""))
            stats_raw = digest.get("stats_json", "") or ""
            articles = 0
            stats: dict[str, Any] = {}
            try:
                parsed_stats = json.loads(stats_raw)
                stats = parsed_stats if isinstance(parsed_stats, dict) else {}
                articles = int(stats.get("articles_count", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
            cost = _digest_cost_usd(store, d_id, d_at, stats)
            recent_digests.append({
                "digest_id": d_id,
                "created_at": d_at,
                "cost_usd": cost,
                "articles": articles,
            })

        # Average cost per digest: total all-time spending / total digest count.
        avg_cost_per_digest_usd = 0.0
        if "spending" in store.db.table_names() and "digests" in store.db.table_names():
            try:
                digest_count_rows = list(store.db.query(
                    "SELECT COUNT(*) as n FROM digests"
                ))
                total_digests = int(
                    digest_count_rows[0]["n"] or 0
                ) if digest_count_rows else 0
                all_spend_rows = list(store.db.query(
                    "SELECT SUM(amount_usd) as total FROM spending"
                ))
                all_time_usd = float(
                    all_spend_rows[0]["total"] or 0
                ) if all_spend_rows else 0.0
                if total_digests > 0:
                    avg_cost_per_digest_usd = all_time_usd / total_digests
            except Exception:
                pass

        return JSONResponse({
            "openrouter": openrouter_data,
            "local": {
                "today_usd": today_usd,
                "month_usd": month_usd,
                "daily_limit_usd": merged.llm.openrouter_daily_budget_usd,
                "monthly_limit_usd": merged.llm.openrouter_monthly_budget_usd,
                "avg_cost_per_digest_usd": avg_cost_per_digest_usd,
                "by_model": by_model,
                "recent_digests": recent_digests,
            },
        })

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

    # --- Read tracking -------------------------------------------------

    @app.get("/api/read", response_model=None)
    async def api_get_read() -> JSONResponse:
        urls = sorted(store.get_read_urls())
        return JSONResponse({"urls": urls})

    @app.post("/api/read", response_model=None)
    async def api_mark_read(body: dict[str, Any]) -> JSONResponse:
        url = str(body.get("url", "")).strip()
        is_read = bool(body.get("read", True))
        if not url:
            return JSONResponse({"error": "Missing url"}, status_code=422)
        if is_read:
            article = store.get_article(url)
            title = str(article["title"]).strip() if article and article.get("title") else None
            store.mark_article_read(url, title=title)
        else:
            store.mark_article_unread(url)
        return JSONResponse({"ok": True})

    # --- Read Later ----------------------------------------------------

    @app.get("/api/read-later", response_model=None)
    async def api_get_read_later() -> JSONResponse:
        """Return all items saved for later, newest first."""
        items = store.list_read_later()
        # Attach current ratings so the UI can show stars.
        items = _attach_ratings(store, items)
        return JSONResponse({"items": items})

    @app.post("/api/read-later", response_model=None)
    async def api_save_read_later(body: dict[str, Any]) -> JSONResponse:
        """Save a digest item to the read-later list.

        The client sends the full DigestItem payload so we can store it
        without needing to look it up from a digest (which may not exist
        in archived digests or after a new run overwrites the latest).
        """
        url = str(body.get("url", "")).strip()
        if not url:
            return JSONResponse({"error": "Missing url"}, status_code=422)
        store.save_read_later(body)
        return JSONResponse({"ok": True})

    @app.delete("/api/read-later", response_model=None)
    async def api_remove_read_later(body: dict[str, Any]) -> JSONResponse:
        """Remove a URL from the read-later list (mark as done / read)."""
        url = str(body.get("url", "")).strip()
        if not url:
            return JSONResponse({"error": "Missing url"}, status_code=422)
        store.remove_read_later(url)
        return JSONResponse({"ok": True})

    @app.get("/api/read-later/urls", response_model=None)
    async def api_get_read_later_urls() -> JSONResponse:
        """Return only the set of URLs saved for later (lightweight check)."""
        urls = sorted(store.get_read_later_urls())
        return JSONResponse({"urls": urls})

    # --- Preference profile --------------------------------------------

    @app.get("/api/preferences/profile", response_model=None)
    async def api_preferences_profile() -> JSONResponse:
        return JSONResponse(preferences.profile_summary())

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

    if spa_dist.is_dir():
        from starlette.responses import FileResponse

        assets_dir = spa_dist / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="spa-assets",
            )

        @app.get("/{full_path:path}", response_model=None, include_in_schema=False)
        async def spa_catchall(full_path: str) -> Response:
            candidate = spa_dist / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(spa_dist / "index.html"))

    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _sum_spending(store: ContentStore, where: str) -> float:
    if "spending" not in store.db.table_names():
        return 0.0
    try:
        rows = list(store.db.query(
            f"SELECT SUM(amount_usd) as total FROM spending WHERE {where}"
        ))
        return float(rows[0]["total"] or 0) if rows else 0.0
    except Exception:
        return 0.0


def _digest_cost_usd(
    store: ContentStore,
    digest_id: Any,
    created_at: str,
    stats: dict[str, Any],
) -> float:
    stats_cost = _stats_cost_usd(stats)
    if stats_cost > 0:
        return stats_cost

    if not created_at or "spending" not in store.db.table_names():
        return 0.0

    try:
        parsed_digest_id = int(digest_id)
    except (TypeError, ValueError):
        parsed_digest_id = 0

    explicit_cost = _explicit_digest_cost_usd(store, parsed_digest_id)
    if explicit_cost > 0:
        return explicit_cost

    return _historical_digest_cost_usd(store, parsed_digest_id, created_at)


def _stats_cost_usd(stats: dict[str, Any]) -> float:
    try:
        return float(stats.get("cost_usd", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _explicit_digest_cost_usd(store: ContentStore, digest_id: int) -> float:
    if digest_id <= 0 or not _spending_has_column(store, "digest_id"):
        return 0.0
    try:
        rows = list(store.db.query(
            "SELECT SUM(amount_usd) as total FROM spending WHERE digest_id = ?",
            [digest_id],
        ))
        return float(rows[0]["total"] or 0) if rows else 0.0
    except Exception:
        return 0.0


def _historical_digest_cost_usd(
    store: ContentStore,
    digest_id: int,
    created_at: str,
) -> float:
    try:
        previous_rows = list(store.db.query(
            "SELECT created_at FROM digests"
            " WHERE id < ? ORDER BY id DESC LIMIT 1",
            [digest_id],
        ))
        previous_created_at = (
            str(previous_rows[0]["created_at"] or "")
            if previous_rows else ""
        )
        where = "recorded_at <= ?"
        params: list[Any] = [created_at]
        if previous_created_at:
            where = f"recorded_at > ? AND {where}"
            params.insert(0, previous_created_at)
        rows = list(store.db.query(
            f"SELECT SUM(amount_usd) as total FROM spending WHERE {where}",
            params,
        ))
        return float(rows[0]["total"] or 0) if rows else 0.0
    except Exception:
        return 0.0


def _spending_has_column(store: ContentStore, column: str) -> bool:
    try:
        return any(
            row[1] == column
            for row in store.db.execute("PRAGMA table_info(spending)").fetchall()
        )
    except Exception:
        return False


def _build_digest_detail(
    row: dict[str, Any],
    store: ContentStore | None = None,
) -> dict[str, Any]:
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
