# Configuration

## Files

- `config.yaml` (or path from `CONDENSEIT_CONFIG`) holds feeds, YouTube channels,
  LLM provider, budgets, email, and VPS settings.
- `CONDENSEIT_DATA_DIR` (default `./data`) holds SQLite, digests on disk, and keys.
- `CONDENSEIT_FRONTEND_DIST` (optional): directory with the Vite SPA output
  (`index.html` and assets). Docker Compose sets this to `/app/frontend/dist` so
  the app does not fall back to legacy Jinja pages when the package is installed
  under `site-packages`.

## LLM

- `llm.provider`: `ollama`, `openrouter`, or `fallback` (local then cloud).
- `llm.openrouter_pick_cheapest`: when `true`, the cheapest suitable text model from
  the public OpenRouter catalog is chosen (cached about one hour). You still need
  an API key for requests.
- `llm.openrouter_daily_budget_usd` / `openrouter_monthly_budget_usd`: spend caps.

## Preferences

- `relevance.tfidf_preference_weight`: blend of cosine similarity between article
  tokens and a profile built from your star ratings (set `0` to disable).

## Scheduling

CondenseIt does not daemonize itself. Use cron, systemd timers, or launchd.
See [scheduling.md](scheduling.md) for Linux and macOS examples, and the sample
plist under `launchd/`. The `bash scripts/install.sh` helper can emit cron lines
and a plist from a chosen time and cadence (see [installation.md](installation.md)).

## Email (Resend)

- `config.yaml` `email` section: `enabled`, `from`, `to`, and optional
  `resend_api_key` (often `${RESEND_API_KEY}` so the secret stays in `.env`).
- On startup, if a `.env` file exists next to `config.yaml` or in the current
  working directory, it is loaded first (without overriding variables already
  set in the process).
- **Precedence:** `RESEND_FROM` and `DIGEST_EMAIL_TO`, when non-empty after
  `load_config` reads YAML, **replace** `email.from` and `email.to`. `RESEND_API_KEY`
  replaces `email.resend_api_key` when set. The Resend API key can also live in
  the admin key store under `resend` instead of config.
