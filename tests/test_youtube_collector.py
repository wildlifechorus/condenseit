"""Tests for YouTube RSS description extraction."""

from __future__ import annotations

from condenseit.collectors.youtube import YouTubeCollector


def test_entry_plain_text_from_summary_detail_strips_html() -> None:
    entry = {
        "summary_detail": {
            "type": "text/html",
            "value": "<p>Hello &amp; <b>world</b></p>",
        },
    }
    assert YouTubeCollector._entry_plain_text(entry) == "Hello & world"


def test_entry_plain_text_falls_back_to_summary() -> None:
    entry = {"summary": "  Plain summary text  "}
    assert YouTubeCollector._entry_plain_text(entry) == "Plain summary text"


def test_entry_plain_text_falls_back_to_content_list() -> None:
    entry = {
        "content": [{"type": "text/html", "value": "<div>From content</div>"}],
    }
    assert YouTubeCollector._entry_plain_text(entry) == "From content"


def test_entry_plain_text_empty() -> None:
    assert YouTubeCollector._entry_plain_text({}) == ""
