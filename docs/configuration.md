# Configuration

## Files

- `config.yaml` (or path from `CONDENSEIT_CONFIG`) holds feeds, YouTube channels,
  LLM provider, budgets, and VPS settings.
- `CONDENSEIT_DATA_DIR` (default `./data`) holds SQLite, digests on disk, and keys.
- `CONDENSEIT_FRONTEND_DIST` (optional): directory with the Vite SPA output
  (`index.html` and assets). Docker Compose sets this to `/app/frontend/dist` so
  the app does not fall back to legacy Jinja pages when the package is installed
  under `site-packages`.

## Sources

All sources are managed from **Admin > Sources** in the web UI. Changes take effect
on the next digest run with no restart needed. The following source types are supported.

![Admin sources page with generated demo data](assets/demo/desktop-admin-sources.png)

### RSS / Atom

Any public RSS or Atom feed URL. Most news sites, blogs, and podcasts publish one.

```yaml
feeds:
  - url: "https://www.example.com/rss"
    category: "General News"
    priority: 2
```

### YouTube

Collects transcripts (or RSS descriptions as fallback) from the most recent videos
of a channel. Requires the channel's `channel_id` (found on the channel's About page).

```yaml
youtube_channels:
  - handle: "@example"
    channel_id: "UCxxxxxxxxxxxxxxxxxxxxxxxxx"
    category: "Tech"
```

### Website watch

Fetches a page on every digest run and reports meaningful content changes. Useful for
pages that do not publish a feed (changelogs, status pages, release notes pages).

```yaml
watch_urls:
  - url: "https://example.com/changelog"
    category: "Developer News"
    selector: null        # CSS selector (not yet used by the fetcher)
    change_threshold: 0.05  # fraction of lines that must change to trigger
```

### Google News search

Queries the Google News public RSS search endpoint. Supports all standard Google
search operators: `site:`, `when:`, `intitle:`, `source:`, `inurl:`, etc. No API
key is required.

Example queries:

| Query | What it returns |
|-------|----------------|
| `site:reuters.com when:1d` | Reuters articles published in the last 24 hours |
| `CVE intitle:critical when:7d` | Critical CVE headlines from the past week |
| `"supply chain" site:bleepingcomputer.com` | Supply-chain articles on Bleeping Computer |

Add via **Admin > Sources**, select type **Google News search**, and enter the query
string. The RSS URL is constructed and previewed automatically.

### Hacker News

Fetches stories from the [official HN Firebase JSON API](https://hacker-news.firebaseio.com/v0/).
No authentication required.

Options (configurable in the add-source form):

| Field | Default | Description |
|-------|---------|-------------|
| Feed | `top` | `top`, `best`, `new`, `ask`, or `show` |
| Min score | `50` | Skip stories below this upvote count |
| Max items | `20` | Maximum stories per digest run |

### Reddit

Fetches posts from any public subreddit via Reddit's public `.json` endpoint.
No API key is required.

Options:

| Field | Default | Description |
|-------|---------|-------------|
| Subreddit | (required) | Name without `r/`, e.g. `netsec` |
| Sort | `hot` | `hot`, `new`, `top`, or `rising` |
| Time filter | `day` | For `top` sort: `hour`, `day`, `week`, `month`, `year`, `all` |
| Min score | `10` | Skip posts below this upvote count |
| Max items | `20` | Maximum posts per digest run |

### GitHub Releases

Tracks new releases for any public GitHub repository via its public Atom feed
(`https://github.com/{owner}/{repo}/releases.atom`). No authentication required.

Enter the repository in `owner/repo` format, e.g. `astral-sh/uv` or `ollama/ollama`.

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

## Preferences and ranking

The ranking engine learns from both explicit star ratings and implicit engagement
signals. All weights can be adjusted live in **Admin > Settings > Ranking weights**
without restarting the server.

### Explicit ratings

Each article you rate 4-5 stars contributes positively to the term-level profile,
category preference, and source preference. Articles rated 1-2 stars contribute
negatively. 3-star ratings are neutral for terms but still influence category/source
averages. After `min_ratings_for_learning` ratings, the engine becomes active.

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.min_ratings_for_learning` | `5` | Ratings needed before learning activates |
| `relevance.tfidf_preference_weight` | `0.35` | Term-level cosine similarity weight (set `0` to disable) |
| `relevance.category_preference_weight` | `0.6` | Per-category mean-rating weight |
| `relevance.source_preference_weight` | `0.3` | Per-source mean-rating weight |
| `relevance.rating_decay_half_life_days` | `30` | Older ratings decay exponentially; this is the half-life in days |

### Implicit signals

Beyond explicit ratings, the engine learns from three engagement signals:

| Signal | Interpretation | Virtual rating equivalent |
|--------|---------------|--------------------------|
| Mark as read | Mild positive interest (you engaged with it) | 3.8 stars |
| Save for later | Strong positive interest | 4.5 stars |
| Dismiss | Mild disinterest (you saw it, not interested) | 1.5 stars |

- `relevance.implicit_signal_weight` (default `0.5`): scales the total contribution
  of implicit signals relative to explicit ratings. Set to `0` to disable implicit
  learning entirely.

### Score breakdown

Every ranked article receives a `score_breakdown` dict stored in `digest_items`.
The digest card in the admin UI shows a collapsible "Why ranked here?" section
listing each contributing signal (keyword hits, term overlap, TF-IDF, category,
source, implicit content/category/source, synonym boost).

### Topic synonyms

Optional synonym groups let the engine propagate profile weight across related
terms. Defined in `config.yaml` under `relevance.topic_synonyms`:

```yaml
relevance:
  topic_synonyms:
    kubernetes: ["k8s", "helm", "kubectl"]
    security:   ["infosec", "cybersecurity", "appsec"]
```

When an article mentions `k8s`, the engine checks the profile for `kubernetes` and
vice versa, boosting or penalising the article accordingly.

### Learning profile

The full learned profile (category scores, source scores, liked/disliked topics
and phrases, rating distribution, implicit signal counts, decay info) is visible
in **Admin > Preferences**.

![Learning profile page with generated demo data](assets/demo/desktop-preferences.png)

## Scheduling

Set `CONDENSEIT_SCHEDULER_ENABLED=1` in `.env` and start `condenseit serve`.
The built-in scheduler runs digests at the times configured in **Admin > Schedule**
(stored in the DB, overriding `config.schedule.times`). No cron, systemd timer,
or launchd entry is needed. See [scheduling.md](scheduling.md) for details.

If you prefer external scheduling (cron, systemd, launchd), the
`bash scripts/install.sh` helper can emit ready-to-paste snippets for your
chosen time and cadence (see [installation.md](installation.md)).
