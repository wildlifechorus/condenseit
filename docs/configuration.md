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

Any public RSS or Atom feed URL. Most news sites and blogs publish one.

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

### Podcasts

Tracks new podcast episodes from a public podcast RSS feed. The Add Source form
can search the iTunes podcast catalog and auto-fill the feed URL, or you can paste
the feed URL directly. No API key is required.

Episode summaries are generated from the podcast show notes in the RSS feed.
Episode or channel artwork is used when the feed provides it.

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
- `max_key_takeaways` (default `5`, range 1-10): number of bullet-point
  takeaways the LLM generates per article.
- `max_summary_paragraphs` (default `5`, range 1-10): number of paragraphs in
  the LLM-generated article summary.
- `preferred_languages`: ISO 639-1 codes (e.g. `["en", "pt"]`). Leave empty to
  accept all languages. Language detection uses `langdetect`.

## Preferences and ranking

CondenseIt uses a multi-layer ranking engine that blends classical signals with
optional AI layers. All weights are adjustable live in **Admin > Digest** without
restarting the server.

### Ranking pipeline

Each digest run processes articles in this order:

1. **Collect** - pull from all enabled sources
2. **Filter** - age gate, already-read filter, language filter, excluded keywords
3. **Classical score** - score every candidate using the preference engine
4. **Embedding score** - add semantic similarity to your rated-article centroid (optional)
5. **Story deduplication** - keep the highest-scoring version of near-duplicate stories
6. **LLM rerank** - one LLM call re-orders the top-K candidates (optional)
7. **Category balance** - reserve slots per category, then fill by score
8. **Summarise** - per-article LLM call that also extracts topics, entities, and novelty
9. **Persist** - save digest items and enrichment data for future ranking

### Classical scoring

The classical scorer assigns each article a `preference_score` that is the sum of
up to eleven named signals. All weights default to sensible values and can be set
to `0` to disable a specific signal entirely.

| Signal | `score_breakdown` key | What drives it |
|--------|----------------------|---------------|
| Keyword high | `keyword_high` | Matches `relevance.initial_keywords.high` terms |
| Keyword medium | `keyword_medium` | Matches `relevance.initial_keywords.medium` terms |
| Term overlap | `term_overlap` | Bag-of-words overlap with your liked terms |
| Bigram overlap | `bigram_overlap` | Two-word phrase overlap with your liked bigrams |
| TF-IDF cosine | `tfidf_cosine` | Cosine similarity between article and liked-article TF-IDF vectors |
| Category | `category` | Mean rating deviation for the article's category |
| Source | `source` | Mean rating deviation for the article's source |
| Implicit content | `implicit_content` | Content profile built from read/saved/dismissed signals |
| Implicit category | `implicit_category` | Category signal from implicit engagement |
| Implicit source | `implicit_source` | Source signal from implicit engagement |
| Synonym boost | `synonym_boost` | Weight propagated via `relevance.topic_synonyms` groups |

**Explicit rating settings** (live in Admin > Digest, or set in `config.yaml`):

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.min_ratings_for_learning` | `5` | Ratings needed before the engine activates |
| `relevance.tfidf_preference_weight` | `0.35` | TF-IDF cosine similarity weight |
| `relevance.category_preference_weight` | `0.6` | Per-category mean-rating weight |
| `relevance.source_preference_weight` | `0.3` | Per-source mean-rating weight |
| `relevance.rating_decay_half_life_days` | `30` | Exponential half-life for rating age decay (days) |

**Implicit signal settings**:

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.implicit_signal_weight` | `0.5` | Scale factor for implicit signals vs explicit ratings. `0` = disabled |

Implicit actions are treated as virtual ratings:

| Action | Virtual rating |
|--------|--------------|
| Mark as read | 3.8 stars (mild positive) |
| Save for later | 4.5 stars (strong positive) |
| Dismiss | 1.5 stars (mild negative) |

### Time decay

All ratings (explicit and implicit) decay exponentially so recent behaviour
dominates over stale preferences. After `rating_decay_half_life_days` days a
rating contributes half as much as it did when first recorded. The current decay
weight of your oldest rating is shown in **Admin > Preferences**.

### Topic synonyms

Synonym groups let the engine propagate profile weight across related terms
without separate ratings. Defined in `config.yaml`:

```yaml
relevance:
  topic_synonyms:
    kubernetes: ["k8s", "helm", "kubectl"]
    security:   ["infosec", "cybersecurity", "appsec"]
```

When an article mentions `k8s`, the engine looks up the `kubernetes` profile entry
and vice versa. The synonym boost appears as `synonym_boost` in the score breakdown.

### AI-powered ranking

Three optional AI layers sit on top of classical scoring. Each is independently
controlled, off by default, and fail-open (a broken LLM or network error falls
back to classical ranking silently).

All AI settings are in **Admin > Digest** under the AI Ranking section, or in
`config.yaml` under `relevance.*`.

#### Layer 1: Semantic embeddings

Articles are encoded as fixed-length vectors. The engine builds a
decay-weighted centroid of your liked articles and a centroid of your disliked
articles. Each candidate is scored by:

```
embedding_similarity = cosine(article, liked_centroid)
                     - 0.5 * cosine(article, disliked_centroid)
```

Embeddings are computed once per article and cached in SQLite (keyed by URL,
content hash, and model), so re-running digests does not re-embed known articles.

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.embedding_provider` | `"off"` | `"ollama"`, `"openrouter"`, or `"off"` |
| `relevance.embedding_model` | `"nomic-embed-text"` | Embedding model name |
| `relevance.embedding_preference_weight` | `0.5` | Weight of the embedding signal in the final score |

Recommended models:
- **Ollama (free)**: `nomic-embed-text` - fast, strong quality, requires the model to be pulled once
- **OpenRouter**: `openai/text-embedding-3-small` - $0.02 per million tokens, high quality; a full digest run typically costs under $0.001

##### Semantic duplicate detection

When an embedding provider is active, the pipeline runs a second dedup pass after the existing title-similarity filter. Articles covering the same event across different sources are clustered by cosine similarity; only the highest-ranked article in each cluster makes it into the digest.

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.semantic_dedup_enabled` | `true` | Enable embedding-based story dedup (requires `embedding_provider != "off"`) |
| `relevance.semantic_dedup_threshold` | `0.85` | Cosine similarity above which two articles are treated as the same story |

Threshold guidance:

- **0.90+**: only near-identical wording removed; lowest false-positive risk
- **0.85 (default)**: catches same-event cross-source duplicates with rare false positives
- **0.80**: aggressive; may merge topically related but genuinely distinct stories

Both settings are adjustable in **Admin > Settings** under the "Semantic embeddings" card without restarting the server.

#### Layer 2: LLM topic enrichment

Every article summary call now also extracts structured metadata from the same
JSON response - no extra LLM calls are needed:

- `topics` - 3-7 lowercased semantic topic tags (e.g. `["open-source", "llm", "security"]`)
- `entities` - named people, organisations, and products mentioned
- `novelty` - integer 1-5 rating of how unexpected this story is vs mainstream coverage

These are stored in an `article_enrichment` table. The engine builds a
topic preference profile from your ratings: liked topics get boosted, disliked
topics get penalised. Topics and a "novel" badge are shown on each article card.

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.topic_score_weight` | `0.3` | Weight of the topic-profile overlap signal |

Topic enrichment activates automatically once you have rated articles that have
been summarised. No configuration is required beyond setting a non-zero weight.

#### Layer 3: LLM reranker

After classical and embedding scoring, the engine builds a compact profile
narrative from your top liked/disliked terms, categories, sources, and topics.
A single LLM call scores the top-K candidates by relevance to your profile
and returns a short reason for each. The LLM score is blended with the
classical score:

```
final_score = (1 - blend) * classical_score + blend * llm_relevance_score
```

The reason string is stored in `score_breakdown.llm_reason` and shown in the
"Why ranked here?" panel on each article card.

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.llm_rerank_enabled` | `false` | Enable the rerank pass |
| `relevance.llm_rerank_model` | `""` | Model for reranking. Empty = use the summariser model |
| `relevance.llm_rerank_top_k` | `30` | Candidates sent to the LLM (1-200) |
| `relevance.llm_rerank_blend` | `0.3` | LLM score weight (0 = ignore, 1 = replace classical) |

**Cost**: one call per digest run, ~5K input tokens, ~500 output tokens. Using a
cheap model like `deepseek/deepseek-v3` on OpenRouter costs under $0.005 per run.
`llm_rerank_blend: 0.3` is a safe starting point; increase it once you are happy
with the quality.

### Cold-start bootstrap

The AI layers and classical scorer both benefit from an initial preference profile.
If you have fewer than `min_ratings_for_learning` ratings, visit **Admin > Preferences**
and describe your interests in plain text. The LLM converts your description into:

- `high_keywords` - 5-10 high-priority interest terms
- `medium_keywords` - 5-10 secondary interest terms
- `dislikes` - 3-5 topics to de-prioritise
- `synonyms` - 2-4 synonym groups to extend keyword reach
- `profile_summary` - a 1-2 sentence description of you as a reader

These are saved to the database and used immediately. YAML keywords from
`config.yaml` take precedence; bootstrap values fill gaps. Even after learning
activates you can re-run bootstrap at any time from **Admin > Preferences** using
the "Re-seed with AI" link in the status bar.

Available via API: `POST /api/preferences/bootstrap` with body `{"interests": "..."}`.

### Score breakdown

Every ranked article has a `score_breakdown` dict that shows exactly what drove
its position. It is visible in the "Why ranked here?" collapsible panel on each
article card.

| Key | Type | Description |
|-----|------|-------------|
| `keyword_high` | float | Contribution from high-priority keyword hits |
| `keyword_medium` | float | Contribution from medium-priority keyword hits |
| `term_overlap` | float | Bag-of-words overlap with liked terms |
| `bigram_overlap` | float | Two-word phrase overlap |
| `tfidf_cosine` | float | TF-IDF cosine similarity to liked-article vectors |
| `category` | float | Per-category mean-rating deviation |
| `source` | float | Per-source mean-rating deviation |
| `implicit_content` | float | Content profile from implicit signals |
| `implicit_category` | float | Category signal from implicit engagement |
| `implicit_source` | float | Source signal from implicit engagement |
| `synonym_boost` | float | Synonym group propagation |
| `embedding_similarity` | float | Embedding centroid cosine similarity (0 when disabled) |
| `topic_score` | float | LLM topic-profile overlap (0 when disabled) |
| `llm_rerank` | float | LLM reranker blend contribution (0 when disabled) |
| `llm_reason` | string | Human-readable reason from the LLM reranker |

### Learning profile

**Admin > Preferences** shows the full learned state:

- Learning status (active/inactive) and rating count
- "Semantic profile active" badge when an embedding centroid has been built
- Rating distribution histogram (1-5 stars)
- Engagement signal counts (read, saved, dismissed)
- Time decay info (half-life and oldest rating weight)
- Per-category score bars
- Per-source score bars
- Content terms cloud (TF-IDF keyword profile, sized by weight)
- Keyword phrases cloud (bigram profile)
- AI-extracted topics cloud (from LLM enrichment, when available)

![Learning profile page with generated demo data](assets/demo/desktop-preferences.png)

## Scheduling

Set `CONDENSEIT_SCHEDULER_ENABLED=1` in `.env` and start `condenseit serve`.
The built-in scheduler runs digests at the times configured in **Admin > Schedule**
(stored in the DB, overriding `config.schedule.times`). No cron, systemd timer,
or launchd entry is needed. See [scheduling.md](scheduling.md) for details.

### Timezone

By default all schedule times are treated as UTC. Set your timezone in
**Admin > Schedule** or in `config.yaml` under `schedule.timezone`:

```yaml
schedule:
  timezone: "America/New_York"  # IANA timezone name
  times: ["07:00", "18:00"]
```

Use any [IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)
(e.g. `Europe/London`, `Asia/Tokyo`, `America/Los_Angeles`). The setting is
stored in the database when saved via the UI, which overrides the YAML value.
The next-run time shown in the admin panel is displayed in both your local
timezone and UTC.

If you prefer external scheduling (cron, systemd, launchd), the
`bash scripts/install.sh` helper can emit ready-to-paste snippets for your
chosen time and cadence (see [installation.md](installation.md)).
