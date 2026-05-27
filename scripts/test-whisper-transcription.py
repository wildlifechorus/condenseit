#!/usr/bin/env python3
"""
Manual test for YouTube Whisper transcription via OpenRouter.

Usage:
    uv run python scripts/test-whisper-transcription.py [VIDEO_ID_OR_URL]

If no video is provided, a short 90-second TED-Ed clip is used as the default.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

# --- resolve video ---
DEFAULT_VIDEO = "jNQXAC9IVRw"  # "Me at the zoo" - first ever YouTube video, 19 seconds

arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VIDEO
# Accept full URLs too
if "v=" in arg:
    video_id = arg.split("v=")[1][:11]
elif "youtu.be/" in arg:
    video_id = arg.split("youtu.be/")[1][:11]
else:
    video_id = arg[:11]

print(f"Video ID : {video_id}")
print(f"Watch URL: https://www.youtube.com/watch?v={video_id}")
print()

# --- check prerequisites ---
if not shutil.which("yt-dlp"):
    print("ERROR: yt-dlp not found on PATH. Install with: pip install yt-dlp")
    sys.exit(1)

# load OR key from condenseit config / env
try:
    from condenseit.config import load_config
    from condenseit.store.database import ContentStore
    from condenseit.store.secure_keys import SecureKeyStore

    cfg = load_config()
    store = ContentStore()
    keys = SecureKeyStore(store)
    or_key = keys.get_key("openrouter") or cfg.llm.openrouter_api_key or ""
    store.close()
except Exception as e:
    print(f"ERROR: could not load config: {e}")
    sys.exit(1)

if not or_key:
    print("ERROR: No OpenRouter API key found. Set OPENROUTER_API_KEY or add it in Admin > API Keys.")
    sys.exit(1)

print(f"OpenRouter key : {or_key[:8]}...")
print(f"Whisper model  : {cfg.youtube_transcription.model}")
print()

# --- step 1: first try youtube-transcript-api (existing free path) ---
print("Step 1: Trying youtube-transcript-api (free captions)...")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    chunks = YouTubeTranscriptApi.get_transcript(video_id)
    text = " ".join(c["text"] for c in chunks)
    print(f"  ✓ Captions found ({len(text)} chars). Transcription not needed for this video.")
    print(f"  Preview: {text[:200]}...")
    print()
    print("NOTE: Whisper transcription only fires when captions are unavailable.")
    print("To test Whisper, re-run with a video that has no captions, or pass --force-whisper.")
    force_whisper = "--force-whisper" in sys.argv
    if not force_whisper:
        sys.exit(0)
    print("  --force-whisper passed, continuing anyway...")
except Exception as e:
    print(f"  No captions: {e.__class__.__name__} — proceeding to Whisper.")

print()

# --- step 2: download audio with yt-dlp ---
print("Step 2: Downloading audio with yt-dlp (audio-only, m4a)...")
tmp_dir = Path(tempfile.mkdtemp(prefix="condenseit_whisper_test_"))
audio_path = tmp_dir / "audio.m4a"
url = f"https://www.youtube.com/watch?v={video_id}"

t0 = time.time()
result = subprocess.run(
    [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "m4a",
        "--match-filter", "duration<=1800",
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        "-o", str(audio_path),
        url,
    ],
    capture_output=True,
    text=True,
    timeout=300,
)

if result.returncode != 0 or not audio_path.exists():
    print(f"  ERROR: yt-dlp failed (exit {result.returncode})")
    if result.stderr:
        print(f"  stderr: {result.stderr[:400]}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

file_size_kb = audio_path.stat().st_size // 1024
elapsed = time.time() - t0
print(f"  ✓ Downloaded {file_size_kb} KB in {elapsed:.1f}s → {audio_path}")
print()

# --- step 3: base64 encode ---
print("Step 3: Encoding audio as base64...")
audio_bytes = audio_path.read_bytes()
audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
print(f"  ✓ {len(audio_bytes):,} bytes → {len(audio_b64):,} base64 chars")
print()

# --- step 4: send to OpenRouter Whisper ---
model = cfg.youtube_transcription.model
print(f"Step 4: Sending to OpenRouter ({model})...")
t0 = time.time()
try:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/audio/transcriptions",
        headers={
            "Authorization": f"Bearer {or_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input_audio": {
                "data": audio_b64,
                "format": "m4a",
            },
            "language": "en",
        },
        timeout=300.0,
    )
    resp.raise_for_status()
except httpx.HTTPStatusError as e:
    print(f"  ERROR: HTTP {e.response.status_code}")
    print(f"  Body: {e.response.text[:400]}")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    sys.exit(1)

elapsed = time.time() - t0
data = resp.json()
transcript = str(data.get("text") or "").strip()
usage = data.get("usage") or {}
cost = float(usage.get("total_cost") or 0)

print(f"  ✓ Transcribed in {elapsed:.1f}s")
print(f"  Cost    : ${cost:.6f}" if cost else "  Cost    : (not reported by API)")
print(f"  Tokens  : {usage.get('total_tokens', 'n/a')}")
print(f"  Chars   : {len(transcript)}")
print()
print("=" * 60)
print("TRANSCRIPT:")
print("=" * 60)
print(transcript[:3000])
if len(transcript) > 3000:
    print(f"\n... [{len(transcript) - 3000} more chars]")

# cleanup
shutil.rmtree(tmp_dir, ignore_errors=True)
print()
print("✓ Test complete. Temp audio files cleaned up.")
