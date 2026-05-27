"""Atom feed output for the latest digest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring

register_namespace("", "http://www.w3.org/2005/Atom")

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

from condenseit.store.database import ContentStore


def _parse_stats(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_atom_date(value: str) -> str:
    """Normalise an ISO timestamp to RFC 3339 / Atom format."""
    if not value:
        return _now_iso()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return _now_iso()


def _build_atom(
    digest_row: dict[str, Any] | None,
    feed_url: str,
) -> bytes:
    """Return UTF-8 encoded Atom XML for the given digest row."""
    ns = "http://www.w3.org/2005/Atom"
    feed_el = Element(f"{{{ns}}}feed")

    title_el = SubElement(feed_el, f"{{{ns}}}title")
    title_el.text = "CondenseIt Digest"

    link_self = SubElement(feed_el, f"{{{ns}}}link")
    link_self.set("rel", "self")
    link_self.set("href", feed_url)

    link_alt = SubElement(feed_el, f"{{{ns}}}link")
    link_alt.set("rel", "alternate")
    link_alt.set("href", feed_url.split("/api/")[0] + "/")

    id_el = SubElement(feed_el, f"{{{ns}}}id")
    id_el.text = feed_url

    updated_el = SubElement(feed_el, f"{{{ns}}}updated")

    if digest_row is None:
        updated_el.text = _now_iso()
        return _serialise(feed_el)

    created_at = _to_atom_date(str(digest_row.get("created_at") or ""))
    updated_el.text = created_at

    meta = _parse_stats(str(digest_row.get("stats_json") or ""))
    raw_items = meta.pop("digest_items", None)
    items: list[dict[str, Any]] = raw_items if isinstance(raw_items, list) else []

    for item in items:
        entry = SubElement(feed_el, f"{{{ns}}}entry")

        title = SubElement(entry, f"{{{ns}}}title")
        title.text = str(item.get("title") or "Untitled")

        url = str(item.get("url") or "")
        if url:
            link = SubElement(entry, f"{{{ns}}}link")
            link.set("rel", "alternate")
            link.set("href", url)

        entry_id = SubElement(entry, f"{{{ns}}}id")
        entry_id.text = url or f"condenseit:entry:{item.get('title', '')}"

        published_raw = str(item.get("published_at") or created_at)
        published = SubElement(entry, f"{{{ns}}}published")
        published.text = _to_atom_date(published_raw)

        entry_updated = SubElement(entry, f"{{{ns}}}updated")
        entry_updated.text = created_at

        if item.get("category"):
            cat = SubElement(entry, f"{{{ns}}}category")
            cat.set("term", str(item["category"]))

        if item.get("source"):
            author = SubElement(entry, f"{{{ns}}}author")
            name = SubElement(author, f"{{{ns}}}name")
            name.text = str(item["source"])

        tldr = str(item.get("tldr") or "").strip()
        if tldr:
            summary = SubElement(entry, f"{{{ns}}}summary")
            summary.set("type", "text")
            summary.text = tldr

        content_parts: list[str] = []
        full_summary = str(item.get("summary") or "").strip()
        if full_summary:
            content_parts.append(f"<p>{full_summary}</p>")

        takeaways = item.get("key_takeaways")
        if isinstance(takeaways, list) and takeaways:
            items_html = "".join(f"<li>{t}</li>" for t in takeaways)
            content_parts.append(f"<ul>{items_html}</ul>")

        topics = item.get("topics")
        if isinstance(topics, list) and topics:
            tags = ", ".join(str(t) for t in topics)
            content_parts.append(f"<p><em>Topics: {tags}</em></p>")

        if content_parts:
            content = SubElement(entry, f"{{{ns}}}content")
            content.set("type", "html")
            content.text = "\n".join(content_parts)

    return _serialise(feed_el)


def _serialise(root: Element) -> bytes:
    return b'<?xml version="1.0" encoding="utf-8"?>\n' + tostring(
        root,
        encoding="unicode",
        xml_declaration=False,
    ).encode("utf-8")


def create_feed_router(store: ContentStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/feed/atom", response_model=None)
    async def atom_feed(request: Request) -> Response:
        """Return the latest digest as an Atom feed."""
        digest_row = store.latest_digest()
        token = request.query_params.get("token", "")
        feed_url = str(request.url)
        # Strip the token from the self-link to keep it clean
        base_url = str(request.base_url).rstrip("/")
        self_url = f"{base_url}/api/feed/atom?token={token}" if token else str(request.url)

        xml_bytes = _build_atom(digest_row, self_url)
        return Response(
            content=xml_bytes,
            media_type="application/atom+xml; charset=utf-8",
        )

    return router
