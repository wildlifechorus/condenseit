"""YouTube channel collection via RSS, transcripts, and description fallback."""

from __future__ import annotations

import base64
import html
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import httpx
import sqlite_utils.db
from youtube_transcript_api import YouTubeTranscriptApi

from condenseit.config import YouTubeChannelConfig, YouTubeTranscriptionConfig
from condenseit.fetch_headers import digest_fetch_headers
from condenseit.providers.budget import BudgetTracker
from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/)([a-zA-Z0-9_-]{11})")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MAX_BODY_CHARS = 12000

_OPENROUTER_TRANSCRIPTION_URL = "https://openrouter.ai/api/v1/audio/transcriptions"


def _parse_entry_date(entry: Any) -> str:
    """Return the video's actual publish date from the feed entry, or now() as fallback."""
    if entry.get("published_parsed"):
        t = entry.published_parsed
        return datetime(*t[:6], tzinfo=UTC).isoformat()
    if entry.get("published"):
        try:
            return parsedate_to_datetime(entry.published).isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(UTC).isoformat()


@dataclass
class VideoItem:
    video_id: str
    title: str
    url: str
    channel: str
    category: str
    body: str
    image_url: str | None = field(default=None)
    published_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, str | None]:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.body,
            "source": self.channel,
            "category": self.category,
            "content_hash": ContentStore.content_hash(self.body),
            "published_at": self.published_at,
            "collected_at": datetime.now(UTC).isoformat(),
            "image_url": self.image_url,
        }


class YouTubeCollector:
    def __init__(
        self,
        channels: list[YouTubeChannelConfig],
        store: ContentStore,
        *,
        transcription_config: YouTubeTranscriptionConfig | None = None,
        openrouter_api_key: str = "",
        budget: BudgetTracker | None = None,
    ) -> None:
        self.channels = channels
        self.store = store
        self._transcription = transcription_config
        self._or_key = openrouter_api_key
        self._budget = budget
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers=digest_fetch_headers(),
        )

    @property
    def _whisper_enabled(self) -> bool:
        return bool(
            self._transcription
            and self._transcription.enabled
            and self._or_key
            and shutil.which("yt-dlp")
        )

    def collect_new_videos(self) -> list[VideoItem]:
        videos, _health = self.collect_new_videos_with_health()
        return videos

    def collect_new_videos_with_health(
        self,
    ) -> tuple[list[VideoItem], list[tuple[str, str | None, int]]]:
        """Return ``(videos, [(rss_url, error_or_none, new_video_count), ...])``."""
        videos: list[VideoItem] = []
        health: list[tuple[str, str | None, int]] = []
        for ch in self.channels:
            if not ch.channel_id:
                continue
            rss_url = (
                f"https://www.youtube.com/feeds/videos.xml?channel_id={ch.channel_id}"
            )
            try:
                ch_videos = self._collect_channel(ch)
                videos.extend(ch_videos)
                health.append((rss_url, None, len(ch_videos)))
            except Exception as exc:
                logger.exception("YouTube collect failed for %s", ch.channel_id)
                health.append((rss_url, str(exc), 0))
        return videos, health

    def _collect_channel(self, ch: YouTubeChannelConfig) -> list[VideoItem]:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch.channel_id}"
        resp = self.client.get(rss_url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        label = ch.handle or ch.channel_id
        items: list[VideoItem] = []

        for entry in feed.entries[:5]:
            link = entry.get("link", "")
            vid = _extract_video_id(link)
            if not vid or self._is_processed(vid):
                continue
            transcript = self._fetch_transcript(vid)
            if not transcript and self._whisper_enabled:
                transcript = self._transcribe_via_whisper(vid)
            description = self._entry_plain_text(entry)
            body = (transcript or description).strip()
            if not body:
                logger.debug("No transcript or RSS description for %s", vid)
                continue
            if not transcript:
                logger.info(
                    "Using RSS description for YouTube video %s (no transcript)",
                    vid,
                )
            title = entry.get("title", vid)
            thumbnail = _extract_video_thumbnail(entry, vid)
            items.append(
                VideoItem(
                    video_id=vid,
                    title=title,
                    url=link,
                    channel=label,
                    category=ch.category,
                    body=body[:_MAX_BODY_CHARS],
                    image_url=thumbnail,
                    published_at=_parse_entry_date(entry),
                ),
            )
            self._mark_processed(vid)
        return items

    def _is_processed(self, video_id: str) -> bool:
        try:
            self.store.db["processed_videos"].get(video_id)
            return True
        except (KeyError, sqlite_utils.db.NotFoundError):
            return False

    def _mark_processed(self, video_id: str) -> None:
        self.store.db["processed_videos"].upsert(
            {
                "video_id": video_id,
                "processed_at": datetime.now(UTC).isoformat(),
            },
            pk="video_id",
        )

    @staticmethod
    def _fetch_transcript(video_id: str) -> str:
        try:
            chunks = YouTubeTranscriptApi.get_transcript(video_id)
            joined = " ".join(c["text"] for c in chunks)
            return joined[:_MAX_BODY_CHARS]
        except Exception:
            logger.debug("No transcript for %s", video_id, exc_info=True)
            return ""

    def _transcribe_via_whisper(self, video_id: str) -> str:
        """Download audio with yt-dlp and transcribe via OpenRouter Whisper API."""
        assert self._transcription is not None

        if self._budget and not self._budget.can_spend():
            logger.info("Budget exhausted, skipping Whisper transcription for %s", video_id)
            return ""

        tmp_dir = Path(tempfile.mkdtemp(prefix="condenseit_yt_"))
        audio_path = tmp_dir / "audio.m4a"
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            max_dur = self._transcription.max_duration_seconds
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format", "m4a",
                    "--match-filter", f"duration<={max_dur}",
                    "--no-playlist",
                    "--quiet",
                    "--no-warnings",
                    "-o", str(audio_path),
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0 or not audio_path.exists():
                logger.debug(
                    "yt-dlp failed for %s: %s", video_id, result.stderr[:200]
                )
                return ""

            audio_bytes = audio_path.read_bytes()
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

            resp = httpx.post(
                _OPENROUTER_TRANSCRIPTION_URL,
                headers={
                    "Authorization": f"Bearer {self._or_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._transcription.model,
                    "input_audio": {
                        "data": audio_b64,
                        "format": "m4a",
                    },
                    "language": "en",
                },
                timeout=300.0,
            )
            resp.raise_for_status()
            data = resp.json()
            text = str(data.get("text") or "").strip()

            if self._budget and text:
                usage = data.get("usage") or {}
                cost = float(usage.get("total_cost") or 0)
                if not cost:
                    duration_s = len(audio_bytes) / 16000
                    cost = duration_s * 0.0001
                self._budget.record_spend(
                    cost,
                    model=self._transcription.model,
                    tokens=int(usage.get("total_tokens") or 0),
                )

            if text:
                logger.info(
                    "Whisper transcription succeeded for %s (%d chars)",
                    video_id,
                    len(text),
                )
            return text[:_MAX_BODY_CHARS]

        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp timed out for %s", video_id)
            return ""
        except Exception:
            logger.debug("Whisper transcription failed for %s", video_id, exc_info=True)
            return ""
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def _entry_plain_text(entry: Any) -> str:
        """Best-effort description from the channel RSS/Atom entry."""
        raw = ""
        detail = entry.get("summary_detail")
        if isinstance(detail, dict):
            raw = str(detail.get("value") or "")
        if not raw.strip():
            raw = str(entry.get("summary") or "")
        if not raw.strip():
            content = entry.get("content")
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, dict):
                    raw = str(first.get("value") or "")
        if not raw.strip():
            return ""
        plain = _HTML_TAG_RE.sub(" ", raw)
        plain = html.unescape(plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        return plain[:_MAX_BODY_CHARS]


def _extract_video_thumbnail(entry: Any, video_id: str) -> str:
    """Return the best available thumbnail URL for a YouTube feed entry.

    Prefers ``media:thumbnail`` from the feed (highest quality available).
    Falls back to the standard YouTube HQ thumbnail URL when absent.
    """
    thumbnails = entry.get("media_thumbnail") or []
    if thumbnails and isinstance(thumbnails, list):
        url = thumbnails[0].get("url", "")
        if url:
            return url
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def _extract_video_id(url: str) -> str | None:
    match = _VIDEO_ID_RE.search(url)
    if match:
        return match.group(1)
    if len(url) == 11:
        return url
    return None
