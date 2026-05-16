# Configuration

## Files

- `config.yaml` (or path from `CONDENSEIT_CONFIG`) holds feeds, YouTube channels,
  LLM provider, budgets, and VPS settings.
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

## Digest settings

The following settings can be edited live in the **Admin > Settings** page or
set in `config.yaml`:

- `max_articles_per_digest` (default `50`): total articles per digest run.
- `max_articles_per_category` (default `5`): cap per category when balancing.
- `max_article_age_hours` (default `36`): exclude articles older than this many
  hours. Set to `0` to disable the age gate.
- `balance_digest_categories` (default `true`): reserve a slot per category before
  filling remaining slots by rank.
- `preferred_languages`: ISO 639-1 codes (e.g. `["en", "pt"]`). Leave empty to
  accept all languages. Language detection uses `langdetect`.

## Preferences

- `relevance.tfidf_preference_weight`: blend of cosine similarity between article
  tokens and a profile built from your star ratings (set `0` to disable).
- The learned preference profile (category scores, source scores, liked/disliked
  topics) is visible in **Admin > Preferences**.

## Scheduling

Set `CONDENSEIT_SCHEDULER_ENABLED=1` in `.env` and start `condenseit serve`.
The built-in scheduler runs digests at the times configured in **Admin > Schedule**
(stored in the DB, overriding `config.schedule.times`). No cron, systemd timer,
or launchd entry is needed. See [scheduling.md](scheduling.md) for details.

If you prefer external scheduling (cron, systemd, launchd), the
`bash scripts/install.sh` helper can emit ready-to-paste snippets for your
chosen time and cadence (see [installation.md](installation.md)).
