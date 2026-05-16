# CondenseIt

> Self-hosted AI news digest. Collect RSS feeds, YouTube channels, website
> diffs, Google News searches, Hacker News, Reddit, and GitHub Releases,
> summarize with a local LLM (Ollama) or OpenRouter, learn your preferences
> via star ratings, and read a daily digest in the browser.

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

---

## Two modes

| | Local | Remote |
|-|-------|--------|
| **LLM** | Ollama on your Mac (Metal) | OpenRouter (cloud) |
| **Scheduling** | `condenseit run` from CLI, or `CONDENSEIT_SCHEDULER_ENABLED=1` | Built-in scheduler (`CONDENSEIT_SCHEDULER_ENABLED=1`) |
| **Setup** | `uv sync` + `condenseit serve` | `bootstrap-server.sh` + `deploy.sh` |
| **Cost** | Free (local hardware) | Pay-per-token via OpenRouter |

Both modes use the same unified web UI: digest reader and admin panel.

---

## What it does

CondenseIt pulls from the sources you configure, scores and summarizes each
article with a local or cloud LLM, ranks articles by your learned preferences
(star ratings feed a TF-IDF cosine preference engine), and produces a daily
digest you can read in the browser.

**Supported source types** (all configured from Admin > Sources, no API keys needed):

| Type | What it collects |
|------|-----------------|
| **RSS / Atom** | Any RSS or Atom feed URL |
| **YouTube** | Transcripts from channel videos via the public channel RSS feed |
| **Website watch** | Detects meaningful changes on any web page |
| **Google News search** | Google News RSS search with operator support (`site:`, `when:`, `intitle:`, `source:`) |
| **Hacker News** | Top/best/new/ask/show stories via the public Firebase JSON API |
| **Reddit** | Posts from any public subreddit (hot/new/top/rising, configurable score threshold) |
| **GitHub Releases** | Release notes from any public repository's Atom feed |

### Admin panel

| Page | What it does |
|------|-------------|
| **Sources** | Add/remove all source types; filter by category; set source priority; import/export OPML for RSS feeds |
| **LLM** | Provider, model, OpenRouter cheapest-model option, Ollama pull/delete |
| **API keys** | OpenRouter key storage, encrypted at rest in SQLite |
| **Schedule** | Enable/disable automatic digest runs, set daily run times, and view the next scheduled run |
| **Digest** | Article limits, category balance, article age cutoff, language filter, and summary format |
| **Profile** | Read-only learning profile built from your star ratings |
| **Security** | Change the admin password and warn when the default password is still active |
| **Budget** | OpenRouter account usage, local pipeline cost tracking, and daily/monthly budget limits |
| **Logs** | Full output captured from recent digest runs |

---

## Local mode (Ollama on your Mac)

### Prerequisites

- Python 3.11+, [uv](https://github.com/astral-sh/uv)
- [Ollama](https://ollama.ai) installed and running
- Node.js 18+ (for the frontend build)

### Quick start

```bash
git clone https://github.com/wildlifechorus/condenseit
cd condenseit

# Install dependencies
uv sync

# Pull a model
ollama pull llama3.2:3b

# Build the frontend
cd frontend && npm ci && npm run build && cd ..

# Copy and edit config
cp config.example.yaml config.yaml
cp .env.example .env
# Edit config.yaml: add your feeds, set llm.provider to "ollama" or "openrouter"

# Start the web UI
condenseit serve --port 8899
# Open http://localhost:8899

# Run a digest (in a separate terminal, or from the web UI)
condenseit run
```

### Automatic scheduling

Enable the built-in scheduler in `.env`:

```
CONDENSEIT_SCHEDULER_ENABLED=1
```

Then configure run times in **Admin > Schedule** (or set a default in
`config.schedule.times` in `config.yaml`). Changes made in the admin UI take
effect immediately without a restart.

---

## Remote mode (VPS + OpenRouter)

### Prerequisites

- A VPS with Ubuntu/Debian, SSH access, nginx, and python3
- An [OpenRouter](https://openrouter.ai) API key
- A domain pointed at your VPS

### One-time setup

```bash
# Copy config for your domain
cp scripts/nginx/digest.example.com.conf scripts/nginx/your.domain.conf
# Edit the file: replace "digest.example.com" with your domain

# Set VPS connection details in your local .env
echo 'DIGEST_PWA_SSH_HOST=your-ssh-host' >> .env
echo 'DIGEST_PWA_DOMAIN=your.domain' >> .env
echo 'CONDENSEIT_AUTH_PASSWORD=choose-a-strong-password' >> .env

# Bootstrap the VPS (installs condenseit, systemd service, nginx)
./scripts/bootstrap-server.sh
```

The bootstrap script will prompt for your OpenRouter API key, app password,
and scheduler preference, then write everything to `~/condenseit/.env` on
the VPS. Secrets never touch the systemd unit file.

### Deploy

```bash
./scripts/deploy.sh
```

This builds the frontend, packages a wheel, rsyncs everything to the VPS,
and restarts the service. Run again any time you update sources or config.

### TLS

```bash
ssh your-vps 'sudo certbot --nginx -d your.domain'
```

---

## Configuration

See [`config.example.yaml`](config.example.yaml) and [`.env.example`](.env.example)
for all options with inline comments.

Detailed setup guides:

- [Local deployment](docs/deploy-local.md)
- [VPS deployment](docs/deploy-vps.md)
- [Firebase / Cloud Run deployment](docs/deploy-firebase.md)

Key `config.yaml` sections:

- `llm` - provider (`ollama` / `openrouter` / `fallback`), model, budget limits
- `feeds` / `youtube_channels` / `watch_urls` - legacy YAML-seeded sources (still supported)
- `schedule.times` - default daily run times (overridden by Admin > Schedule)
- `vps` - SSH target for `scripts/deploy.sh`

All sources (including the new types) are managed from **Admin > Sources** in the web UI and stored in SQLite. The YAML keys above act as initial seeds that are imported once on first run.

Settings also editable live in the admin panel (stored in SQLite, no restart needed):

- **Schedule** - run times
- **Digest** - `max_articles_per_digest`, `balance_digest_categories`,
  `max_articles_per_category`, `max_article_age_hours`,
  `preferred_languages`, `max_key_takeaways`, `max_summary_paragraphs`
- **LLM** - provider, model, OpenRouter model, cheapest-model selection
- **Budget** - OpenRouter daily and monthly budget limits
- **Security** - admin password

---

## Budget tracking

When using OpenRouter, the web UI shows a **Budget** page under Admin with:

- OpenRouter account usage (daily / weekly / monthly credits)
- Local spending broken down by model
- Cost per digest run

Budget limits (`openrouter_daily_budget_usd`, `openrouter_monthly_budget_usd`
in `config.yaml`) stop the pipeline before they are exceeded.

---

## Language filtering

Set preferred languages in **Admin > Settings** (ISO 639-1 codes, e.g. `en`,
`pt`, `de`). Articles in other languages are excluded before ranking. Leave
empty to accept all languages. Uses the `langdetect` library; detection
failures always keep the article.

---

## Development

```bash
uv sync --extra dev
pytest -q
ruff check src tests
cd frontend && npm ci && npm run build
```

---

## License

MIT
