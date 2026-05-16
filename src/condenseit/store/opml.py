"""OPML import and export for RSS sources."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any


def parse_opml_outlines(body: str) -> list[dict[str, str]]:
    """Return outline dicts with ``title``, ``xmlUrl`` (RSS), optional ``text``."""
    root = ET.fromstring(body)
    ns = _detect_ns(root)
    out: list[dict[str, str]] = []

    def walk(elem: ET.Element) -> None:
        tag = _strip_ns(elem.tag, ns)
        if tag == "outline":
            xml_url = elem.attrib.get("xmlUrl", "").strip()
            if xml_url and _looks_like_feed(xml_url):
                title = (
                    elem.attrib.get("title") or elem.attrib.get("text") or xml_url
                ).strip()
                out.append({"title": title, "xmlUrl": xml_url})
        for child in elem:
            walk(child)

    walk(root)
    return out


def build_opml(sources: list[dict[str, Any]], title: str = "CondenseIt") -> str:
    """Build OPML 2.0 body from DB source rows (RSS only)."""
    esc_title = html.escape(title, quote=True)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "<head>",
        f"<title>{esc_title}</title>",
        "</head>",
        "<body>",
    ]
    for s in sources:
        if s.get("type") != "rss":
            continue
        url = str(s.get("url", ""))
        if not url:
            continue
        name = html.escape(str(s.get("name") or url), quote=True)
        u_esc = html.escape(url, quote=True)
        lines.append(
            f'<outline type="rss" text="{name}" title="{name}" xmlUrl="{u_esc}" />',
        )
    lines.extend(["</body>", "</opml>"])
    return "\n".join(lines) + "\n"


def _detect_ns(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        m = re.match(r"\{([^}]+)\}", root.tag)
        return m.group(1) if m else ""
    return ""


def _strip_ns(tag: str, ns: str) -> str:
    if ns and tag.startswith("{" + ns + "}"):
        return tag[len(ns) + 2 :]
    return tag


def _looks_like_feed(url: str) -> bool:
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")
