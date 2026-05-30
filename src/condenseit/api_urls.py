"""Stable third-party API base URLs used by collectors and providers."""

import os

OPENROUTER_API_BASE = os.environ.get(
    "OPENROUTER_API_BASE",
    "https://openrouter.ai/api/v1",
)
OPENROUTER_KEY_URL = f"{OPENROUTER_API_BASE}/key"
OPENROUTER_CHAT_URL = f"{OPENROUTER_API_BASE}/chat/completions"
OPENROUTER_EMBEDDINGS_URL = f"{OPENROUTER_API_BASE}/embeddings"
OPENROUTER_TRANSCRIPTIONS_URL = f"{OPENROUTER_API_BASE}/audio/transcriptions"
OPENROUTER_MODELS_URL = f"{OPENROUTER_API_BASE}/models"

REDDIT_WEB_BASE = os.environ.get("REDDIT_WEB_BASE", "https://www.reddit.com")
YOUTUBE_BASE = os.environ.get("YOUTUBE_BASE", "https://www.youtube.com")
YOUTUBE_THUMBNAIL_BASE = os.environ.get(
    "YOUTUBE_THUMBNAIL_BASE",
    "https://img.youtube.com/vi",
)


def youtube_watch_url(video_id: str) -> str:
    return f"{YOUTUBE_BASE}/watch?v={video_id}"


def youtube_channel_feed_url(channel_id: str) -> str:
    return f"{YOUTUBE_BASE}/feeds/videos.xml?channel_id={channel_id}"


def youtube_handle_page_url(handle: str) -> str:
    raw = handle.strip()
    if raw.startswith("@"):
        return f"{YOUTUBE_BASE}/{raw}"
    return f"{YOUTUBE_BASE}/@{raw}"


def youtube_thumbnail_url(video_id: str) -> str:
    return f"{YOUTUBE_THUMBNAIL_BASE}/{video_id}/hqdefault.jpg"
