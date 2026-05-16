from condenseit.digest.format import build_digest_markdown


def test_digest_includes_markdown_links() -> None:
    md = build_digest_markdown(
        {
            "Infosec News": [
                {
                    "title": "Example CVE",
                    "url": "https://example.com/article",
                    "summary": "A critical patch was released.",
                    "source": "Example Blog",
                },
            ],
        },
        changes=[{"url": "https://status.example.com", "status": "changed"}],
        videos=[
            {
                "title": "AI roundup",
                "url": "https://youtube.com/watch?v=abc",
                "summary": "Weekly models overview.",
            },
        ],
    )
    assert "[Example CVE](https://example.com/article)" in md
    assert "[AI roundup](https://youtube.com/watch?v=abc)" in md
    assert "[changed](https://status.example.com)" in md
    assert "https://example.com/article" in md
