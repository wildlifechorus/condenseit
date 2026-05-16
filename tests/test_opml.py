"""OPML parse and build."""

from __future__ import annotations

from condenseit.store.opml import build_opml, parse_opml_outlines


def test_parse_opml_minimal() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0"><head><title>T</title></head><body>
<outline type="rss" text="Example" title="Example"
  xmlUrl="https://example.com/feed.xml" />
</body></opml>"""
    rows = parse_opml_outlines(xml)
    assert len(rows) == 1
    assert rows[0]["xmlUrl"] == "https://example.com/feed.xml"


def test_build_opml_roundtrip_urls() -> None:
    sources = [
        {
            "type": "rss",
            "name": "A",
            "url": "https://a.com/rss",
            "category": "News",
        },
    ]
    body = build_opml(sources)
    back = parse_opml_outlines(body)
    assert any(r["xmlUrl"] == "https://a.com/rss" for r in back)
