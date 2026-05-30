"""Shared browser-like HTTP headers for public digest fetches (RSS, HTML)."""

import os

CONDENSEIT_USER_AGENT_ENV = "CONDENSEIT_USER_AGENT"

# Desktop Chrome on macOS. Override via CONDENSEIT_USER_AGENT when a site is picky.
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)


def digest_fetch_headers() -> dict[str, str]:
    """Return headers for ``httpx`` when fetching feeds and article HTML.

    Reads ``CONDENSEIT_USER_AGENT`` for the ``User-Agent`` value. Empty or
    unset values keep the built-in Chrome-style default.
    """
    raw = os.environ.get(CONDENSEIT_USER_AGENT_ENV, "").strip()
    ua = raw if raw else _DEFAULT_USER_AGENT
    return {
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "application/rss+xml,application/atom+xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
