# Roadmap

This document tracks planned features and improvements for CondenseIt.

## YouTube & Podcast Transcription

### Completed

- **Remote transcription via OpenRouter Whisper**, When YouTube's built-in
  captions are unavailable or low quality, CondenseIt can download the audio
  track with `yt-dlp` and transcribe it using OpenRouter's
  `/api/v1/audio/transcriptions` endpoint (Whisper Large V3 Turbo by default).
  This is opt-in, budget-tracked, and requires `yt-dlp` on the host/server.

### Planned

- **Local Whisper transcription**, Run `faster-whisper` (or `whisper.cpp`) on
  the host machine for zero-cost, offline transcription. Targets Apple Silicon
  Metal acceleration and CUDA on Linux servers. Users would choose between
  `local` and `remote` transcription mode in settings.

  Dependencies for local mode:
  - `faster-whisper` Python package (CTranslate2 backend)
  - A downloaded model file (`base`, `small`, or `medium` depending on
    hardware)
  - On macOS: Metal support via CTranslate2 (M1+ only)
  - On Linux: CUDA toolkit for GPU acceleration (CPU fallback available)

- **Podcast episode transcription**, Apply the same Whisper pipeline to
  podcast audio enclosures. Currently the podcast collector only uses RSS show
  notes; transcribing the actual spoken content would dramatically improve
  summary quality for long-form audio.

- **Transcription cache**, Store transcripts in SQLite keyed by content URL so
  repeat runs never re-transcribe the same episode/video.

- **Selective transcription**, Per-source toggle to enable/disable
  transcription (some channels always have good captions; others never do).

## VPS / Server Dependencies

When deploying to a VPS with YouTube transcription enabled, the server needs:

- `yt-dlp` binary (installable via `pip install yt-dlp` or system package
  manager)
- Sufficient disk space for temporary audio files (~30 MB per 30-min video,
  cleaned up immediately after transcription)
- Network access to `openrouter.ai` (already required if using OpenRouter for
  summarisation)

For future local transcription mode, the VPS would additionally need:

- `faster-whisper` and its CTranslate2 dependency
- A pre-downloaded Whisper model (~150 MB for `base`, ~500 MB for `small`)
- Sufficient RAM (1-2 GB headroom for the model)

## Other Planned Features

_This section will be populated as new feature plans are defined._
