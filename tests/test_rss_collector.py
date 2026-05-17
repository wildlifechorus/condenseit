"""Tests for RSS collection fallbacks."""

from __future__ import annotations

import httpx

from condenseit.collectors.rss import RSSCollector
from condenseit.config import FeedConfig


def test_collect_feed_falls_back_to_urllib_on_403(
    monkeypatch,
) -> None:
    feed_url = "https://blocked.example/feed"
    article_url = "https://blocked.example/post"

    class FakeClient:
        def get(self, url: str) -> httpx.Response:
            request = httpx.Request("GET", url)
            return httpx.Response(403, request=request, text="challenge")

    class FakeHeaders:
        def get_content_charset(self) -> str:
            return "utf-8"

    class FakeUrlopenResponse:
        headers = FakeHeaders()

        def __enter__(self) -> FakeUrlopenResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <rss version="2.0">
                  <channel>
                    <title>Blocked Feed</title>
                    <item>
                      <title>Recovered article</title>
                      <link>{article_url}</link>
                      <description>Recovered summary</description>
                      <pubDate>Sat, 16 May 2026 12:00:00 GMT</pubDate>
                    </item>
                  </channel>
                </rss>
            """.encode()

    def fake_urlopen(request: object, timeout: float) -> FakeUrlopenResponse:
        assert timeout == 30.0
        assert getattr(request, "full_url") == feed_url
        return FakeUrlopenResponse()

    def fake_extract_content(
        self: RSSCollector,
        url: str,
        entry: object,
    ) -> tuple[str, str | None]:
        assert url == article_url
        return "Recovered summary", None

    collector = RSSCollector([FeedConfig(url=feed_url, category="Test")])
    collector.client = FakeClient()

    monkeypatch.setattr("condenseit.collectors.rss.urlopen", fake_urlopen)
    monkeypatch.setattr(RSSCollector, "_extract_content", fake_extract_content)

    articles = collector._collect_feed(FeedConfig(url=feed_url, category="Test"))

    assert len(articles) == 1
    assert articles[0].title == "Recovered article"
    assert articles[0].url == article_url
    assert articles[0].category == "Test"
