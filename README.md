# CondenseIt

> Self-hosted AI news digest. Collect RSS feeds, YouTube channels, and website
> diffs, summarize with a local LLM (Ollama) or OpenRouter, learn your
> preferences via star ratings, and deliver a daily digest by email or static
> PWA.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## What it does

CondenseIt pulls from the sources you configure (RSS, YouTube transcripts,
watched URLs), runs them through a local or cloud LLM to score and summarize
each article, ranks by your learned preferences, and produces a single digest
you can read in the browser, receive by email, or publish as a Progressive Web
App.

**Key ideas:**

- **Runs on your machine.** No cloud account required. Ollama on macOS (Metal)
  is the default; OpenRouter is an optional fallback with spend caps.
- **Learns from you.** Star ratings feed a TF-IDF + cosine preference engine
  that re-ranks future digests.
- **No always-on process.** Schedule `condenseit run` via cron, systemd, or
  launchd. The web UI stays up in Docker for browsing and admin.
- **Optional static PWA.** Rsync the digest to a VPS as an installable web app
  with offline support.

---

## Architecture

| Component | Where it runs |
|-----------|---------------|
| Web UI (digest reader, admin, ratings) | **Docker** on port 8899 |
| `condenseit run` with Ollama | **Host** (Metal on Mac, or any Linux host) |

Docker does **not** run Ollama or LLM jobs. CPU inference inside Docker on Mac
is far too slow; the pipeline runs natively on the host while Docker serves the
UI only.

Shared state: `./data` is bind-mounted into the UI container so digests
produced by native runs appear in the browser immediately.

---

## Quick start

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Docker,
[Ollama](https://ollama.com) (for local LLM).

```bash
git clone https://github.com/wildlifechorus/condenseit
cd condenseit

cp config.example.yaml config.yaml   # edit feeds, channels, and model
cp .env.example .env                  # optional: email, VPS, OpenRouter key

brew install ollama                   # macOS; see ollama.com for Linux
./scripts/native-setup.sh            # venv + ollama pull

make run-with-ollama                  # Docker UI + host digest
```

Open [http://localhost:8899](http://localhost:8899) and click **Run digest** in
the header.

Admin panel: [http://localhost:8899/admin](http://localhost:8899/admin)

---

## Other run modes

| Command | What happens |
|---------|-------------|
| `make run-with-ollama` | Docker UI + native full digest (recommended) |
| `make docker-up` | UI only (browse previous digests) |
| `make run` | Native digest only, no Docker |
| `make run-without-ollama` | Dry run (collectors only, no LLM) |
| `make run-with-ollama-pwa-deploy` | Full digest + deploy static PWA to VPS |
| `condenseit run --dry-run` | Collect and rank, skip LLM summarization |
| `condenseit serve` | Start the web UI on the host (no Docker) |

---

## Features

- **Collectors:** RSS/Atom, YouTube (transcripts + description fallback), website
  change detection, per-source health tracking and backoff
- **LLM:** Ollama (local, Metal on Mac), OpenRouter (cloud, optional cheapest
  model selection), fallback chain, per-provider daily/monthly spend caps
- **Preference learning:** Star ratings, TF-IDF cosine similarity against a
  keyword profile built from your ratings history
- **Admin UI:** HTMX-powered source management (OPML import/export), Ollama
  model pull and delete, API key manager, LLM advisor
- **Delivery:** Resend email (optional), VPS rsync, static PWA (installable,
  offline-capable)
- **Scheduling:** cron, systemd timer, or macOS launchd via example plists in
  `launchd/` and the interactive `bash scripts/install.sh`
- **Zero cloud dependency by default.** OpenRouter, Resend, and VPS deploy are
  all opt-in via `config.yaml` and `.env`.

---

## CLI

```bash
condenseit run [--dry-run] [--no-email] [--no-deploy]
condenseit serve [--host HOST] [--port PORT]
condenseit status
condenseit pwa-build [-o OUTPUT_DIR]
condenseit ratings-import PATH
```

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit:

- `feeds` — RSS/Atom feed URLs
- `youtube_channels` — channel handles (e.g. `@ChannelName`)
- `watch_urls` — pages to diff on each run
- `llm.provider` — `ollama`, `openrouter`, or `fallback`
- `email` — Resend API key + from/to addresses
- `vps` — SSH host + path for static site deploy

Sensitive values (`RESEND_API_KEY`, `OPENROUTER_API_KEY`, etc.) go in `.env`.
See [docs/configuration.md](docs/configuration.md) for the full reference.

---

## Documentation

- [Getting started](docs/getting-started.md)
- [Installation](docs/installation.md)
- [Configuration reference](docs/configuration.md)
- [Shell scripts and Make targets](docs/scripts.md)
- [Scheduling (cron, systemd, launchd)](docs/scheduling.md)
- [Deployment](docs/deployment.md)
- [Digest PWA (static public site)](docs/digest-pwa.md)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and
guidelines.

```bash
uv sync --extra dev
ruff check src tests
pytest tests/
```

Please report security issues privately; see [SECURITY.md](SECURITY.md).

---

## Sanitized config export

```bash
./scripts/export-config.sh
```

Prints `config.yaml` with lines that look like secret keys stripped, safe to
paste when asking for help.

---

## License

[MIT](LICENSE)
