"""Build a static PWA bundle from the latest stored digest.

Strategy:
  1. Read the latest digest from the DB.
  2. Write ``digest-data.json`` to the output directory.
  3. Run ``vite build --mode pwa`` (from the ``frontend/`` directory)
     so the Preact app is compiled with ``import.meta.env.MODE === 'pwa'``.
  4. Copy the app icon and ensure the manifest is up to date.

The Vite build targets ``../data/pwa-dist`` (relative to ``frontend/``),
which can be overridden by passing ``output_dir`` to :func:`build_digest_pwa`.
The app fetches ``/digest-data.json`` at runtime; the Workbox service worker
pre-caches it for offline use.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import markdown

from condenseit.config import AppConfig
from condenseit.providers.base import parse_summary_response
from condenseit.store.database import ContentStore

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_FRONTEND_DIR = _REPO_ROOT / "frontend"
_ASSETS = Path(__file__).resolve().parent / "assets"

# Regex helpers (same logic as web/app.py _clean_summary)
import re as _re

_SUMMARY_PREFIX = _re.compile(
    r"^(?:here\s+is\s+(?:a\s+)?(?:\d+[-\u2013]\d+\s+sentence\s+)?"
    r"(?:brief\s+)?summary[^:]*:|this\s+(?:is\s+(?:a|an)\s+)?"
    r"(?:\d+[-\u2013]\d+\s+sentence\s+)?(?:brief\s+)?summary[^:]*:)\s*",
    _re.IGNORECASE,
)
_NOTE_SUFFIX = _re.compile(r"\n+\s*note:\s.*$", _re.IGNORECASE | _re.DOTALL)


def _clean_summary(raw: str) -> str:
    s = (raw or "").strip()
    s = _SUMMARY_PREFIX.sub("", s)
    s = _NOTE_SUFFIX.sub("", s)
    return s.strip()


def _clean_items(items: list[Any]) -> list[Any]:
    out = []
    for it in items:
        if not isinstance(it, dict):
            out.append(it)
            continue
        row = dict(it)
        if not (row.get("tldr") or row.get("key_takeaways")):
            parsed = parse_summary_response(str(row.get("summary") or ""))
            row["tldr"] = parsed["tldr"]
            row["key_takeaways"] = parsed["key_takeaways"]
            row["summary"] = parsed["summary"]
        row["summary"] = _clean_summary(str(row.get("summary") or ""))
        if row.get("tldr"):
            row["tldr"] = _clean_summary(str(row["tldr"]))
        if not isinstance(row.get("key_takeaways"), list):
            row["key_takeaways"] = []
        out.append(row)
    return out


def build_digest_pwa(
    output_dir: Path,
    store: ContentStore,
    config: AppConfig,
) -> dict[str, Any]:
    """
    Build the static PWA and write files to *output_dir*.

    Returns a summary dict with ``output_dir``, ``digest_id``, and ``bytes``.
    """
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    row = store.latest_digest()
    digest_id = int(row["id"]) if row else 0
    created = str(row.get("created_at", ""))[:19] if row else ""

    # Build digest HTML from markdown if stored HTML is absent
    if row and (row.get("html") or "").strip():
        body_html = str(row["html"])
    elif row and (row.get("markdown") or "").strip():
        body_html = markdown.markdown(
            str(row["markdown"]),
            extensions=["tables", "fenced_code"],
        )
    else:
        body_html = (
            "<p>No digest yet. Run <code>condenseit run</code> on your host, "
            "then <code>condenseit pwa-build</code> again.</p>"
        )

    # Parse structured items
    digest_items: list[Any] = []
    if row and row.get("stats_json"):
        try:
            st = json.loads(str(row["stats_json"]))
            if isinstance(st, dict):
                raw_items = st.get("digest_items")
                if isinstance(raw_items, list):
                    digest_items = raw_items
        except json.JSONDecodeError:
            digest_items = []

    # Build the digest data payload (used by both Vite and fallback paths).
    digest_data = {
        "meta": {
            "id": digest_id,
            "created_at": created,
        },
        "html": body_html,
        "items": _clean_items(digest_items),
        "config": {
            "mergeUrl": (config.digest_pwa.ratings_merge_url or "").strip(),
            "digestId": digest_id,
        },
    }

    # Run Vite PWA build if the frontend directory is present.
    # Set CONDENSEIT_SKIP_VITE_BUILD=1 to use the Python fallback (e.g. in tests).
    # IMPORTANT: Vite is called with --emptyOutDir, so any files written before
    # this call would be deleted. digest-data.json is written after the build.
    import os as _os

    use_vite = _FRONTEND_DIR.is_dir() and not _os.environ.get(
        "CONDENSEIT_SKIP_VITE_BUILD"
    )
    if use_vite:
        _run_vite_build(output_dir)
    else:
        _write_fallback_bundle(output_dir, digest_data, config)

    # Write digest-data.json after Vite so --emptyOutDir does not delete it.
    data_path = output_dir / "digest-data.json"
    data_path.write_text(
        json.dumps(digest_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Copy icon (Vite copies it from frontend/public/ but this ensures it is
    # present for the fallback path or when Vite is skipped).
    icon_src = _ASSETS / "icon.svg"
    if icon_src.is_file():
        shutil.copy2(icon_src, output_dir / "icon.svg")

    byte_count = sum(
        f.stat().st_size for f in output_dir.iterdir() if f.is_file()
    )
    return {
        "output_dir": str(output_dir),
        "digest_id": digest_id,
        "bytes": byte_count,
    }


def _run_vite_build(output_dir: Path) -> None:
    """Invoke ``vite build --mode pwa`` from the frontend directory."""
    import os

    if os.environ.get("CONDENSEIT_SKIP_VITE_BUILD"):
        return

    node = shutil.which("node") or "node"
    npm = shutil.which("npm") or "npm"

    # Ensure node_modules exist
    node_modules = _FRONTEND_DIR / "node_modules"
    if not node_modules.is_dir():
        print("Installing frontend dependencies…", file=sys.stderr)
        subprocess.run(
            [npm, "install"],
            cwd=str(_FRONTEND_DIR),
            check=True,
        )

    print(f"Running vite build --mode pwa → {output_dir}", file=sys.stderr)
    env_extra = {"VITE_PWA_OUT": str(output_dir)}
    result = subprocess.run(
        [
            node,
            "node_modules/.bin/vite",
            "build",
            "--mode",
            "pwa",
            "--outDir",
            str(output_dir),
            "--emptyOutDir",
        ],
        cwd=str(_FRONTEND_DIR),
        env={**_get_env(), **env_extra},
    )
    if result.returncode != 0:
        print(
            "Vite PWA build failed - falling back to legacy HTML generator.",
            file=sys.stderr,
        )


def _get_env() -> dict[str, str]:
    import os

    return dict(os.environ)


def _write_fallback_bundle(
    output_dir: Path,
    digest_data: dict[str, Any],
    config: AppConfig,
) -> None:
    """
    Minimal fallback when the frontend/ directory is not present
    (e.g. installed as a pip package without the source tree).
    Generates a simple readable HTML digest similar to the old pwa/build.py.
    """
    items = digest_data.get("items", [])
    body_html = digest_data.get("html", "")
    meta = digest_data.get("meta", {})
    digest_id = meta.get("id", 0)
    created = meta.get("created_at", "")

    public_url = (config.vps.digest_url or "").rstrip("/")
    canon = ""
    if public_url:
        canon = f'<link rel="canonical" href="{public_url}/">'

    cards_html = ""
    for it in items:
        title = _h(str(it.get("title", "") or "Untitled"))
        url = _h(str(it.get("url", "#")))
        summary = _h(str(it.get("summary", "")))
        source = _h(str(it.get("source", "")))
        category = _h(str(it.get("category", "")))
        kind = _h(str(it.get("kind", "article")))
        cards_html += f"""
<article class="card">
  <div class="meta"><span class="badge">{kind}</span> {category}</div>
  <h3><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h3>
  {f'<p class="source">{source}</p>' if source else ""}
  {f'<p class="summary">{summary}</p>' if summary else ""}
</article>"""

    digest_items_json = json.dumps(items, ensure_ascii=False).replace("<", "\\u003c")
    merge_url = (config.digest_pwa.ratings_merge_url or "").strip()
    cfg_json = json.dumps(
        {"mergeUrl": merge_url, "digestId": digest_id}, separators=(",", ":")
    ).replace("<", "\\u003c")

    css = (
        Path(__file__).resolve().parent.parent / "web" / "static" / "app.css"
    )
    css_tag = '<link rel="stylesheet" href="/app.css">'
    if css.is_file():
        shutil.copy2(css, output_dir / "app.css")

    ratings_js = _ASSETS / "pwa-ratings.js"
    if ratings_js.is_file():
        shutil.copy2(ratings_js, output_dir / "pwa-ratings.js")

    filter_js = (
        Path(__file__).resolve().parent.parent / "web" / "static" / "digest-filter.js"
    )
    filter_tag = ""
    if filter_js.is_file():
        shutil.copy2(filter_js, output_dir / "digest-filter.js")
        filter_tag = '<script src="/digest-filter.js" defer></script>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0d9488">
  <title>CondenseIt Digest #{digest_id}</title>
  {canon}
  <link rel="manifest" href="/manifest.webmanifest">
  {css_tag}
</head>
<body>
  <header class="site-header pwa-site-header">
    <div class="pwa-header-top">
      <div class="brand pwa-brand">
        <span class="brand-mark">C</span>
        <span>CondenseIt Digest</span>
      </div>
    </div>
    <p class="digest-meta pwa-header-meta">{created or "No timestamp"} · digest #{digest_id}</p>
  </header>
  <div class="layout layout--pwa">
    <main class="content content--pwa">
      <section class="digest-panel">
        <div class="digest-browse" id="digest-browse-root">
          <script type="application/json" id="condenseit-digest-items-data">{digest_items_json}</script>
          <ul id="digest-item-list" class="digest-item-list"></ul>
          <div id="digest-filter-empty" class="digest-filter-empty is-hidden"></div>
          <p id="digest-filter-count" class="digest-filter-count"></p>
        </div>
        <details class="digest-prose-details">
          <summary>Show full formatted digest</summary>
          <article class="prose digest-body digest-body--framed">{body_html}</article>
        </details>
        <div id="pwa-ratings-root"></div>
        <script type="application/json" id="condenseit-pwa-ratings-cfg">{cfg_json}</script>
      </section>
    </main>
  </div>
  {filter_tag}
  <script src="/pwa-ratings.js" defer></script>
  <script>if("serviceWorker"in navigator)navigator.serviceWorker.register("/sw.js").catch(()={{}});</script>
</body>
</html>"""

    (output_dir / "index.html").write_text(html, encoding="utf-8")

    manifest = {
        "name": "CondenseIt Digest",
        "short_name": "Digest",
        "description": "Personal AI news digest",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f8fafc",
        "theme_color": "#0d9488",
        "icons": [
            {
                "src": "/icon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
    }
    (output_dir / "manifest.webmanifest").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    sw = _service_worker_js(digest_id)
    (output_dir / "sw.js").write_text(sw, encoding="utf-8")


def _h(s: str) -> str:
    """Minimal HTML-escape for the fallback template."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _service_worker_js(digest_id: int) -> str:
    """Minimal service worker for the fallback bundle."""
    cache = f"condenseit-digest-v{digest_id}"
    core = json.dumps(
        ["/", "/index.html", "/app.css", "/manifest.webmanifest", "/icon.svg",
         "/digest-data.json", "/pwa-ratings.js", "/digest-filter.js"]
    )
    return f"""/* CondenseIt digest PWA - fallback SW */
const CACHE = {json.dumps(cache)};
const CORE = {core};

self.addEventListener("install", (e) => {{
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)));
  self.skipWaiting();
}});

self.addEventListener("activate", (e) => {{
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
}});

self.addEventListener("fetch", (e) => {{
  if (e.request.method !== "GET") return;
  e.respondWith(
    fetch(e.request)
      .then((r) => {{
        if (r.status === 200) {{
          const copy = r.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }}
        return r;
      }})
      .catch(() => caches.match(e.request).then((r) => r || caches.match("/index.html")))
  );
}});
"""
