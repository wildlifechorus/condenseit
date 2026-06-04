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

### Per-source filter rules

Each source can define keyword rules in **Admin > Sources** (add or edit a source,
**Filter rules** section). Rules are stored in the source's `extra_json` in SQLite
and apply on the next digest run with no restart.

Matching is case-insensitive against the article **title** plus the first **500
characters** of its body (or feed summary). You can use `*` as a wildcard: every
non-empty segment between `*` signs must appear in the text. Examples: `CVE-*`
matches any string containing `cve-`; `GHSA-*` matches `ghsa-`; `*patch*` matches
`patch`.

| Rule | UI label | Effect |
|------|----------|--------|
| **Show only if** | `require_keywords` | Allowlist. If the list is non-empty, articles that match **none** of these keywords are dropped during collection (before they are stored). |
| **Hide keywords** | `hide_keywords` | Blocklist. Articles matching any keyword are dropped. |
| **Highlight keywords** | `highlight_keywords` | Articles matching any keyword are kept, get a +2.0 preference score boost after ranking, and show a **Highlighted** badge in the digest. |

Rules are evaluated in order: hide, then show-only, then highlight. Hide and
show-only both remove articles from the pipeline; highlight only affects ranking
and display.

Example: track the [Next.js releases Atom feed](https://github.com/vercel/next.js/releases.atom)
but only surface security-related releases. Set **Show only if** to terms such as
`security`, `vulnerability`, `CVE-*`, `GHSA-*`, `patch`, `advisory`, `disclosure`.
Regular version releases without those terms are filtered out; a CVE advisory
release is kept and can be highlighted further if you add `vulnerability` under
**Highlight keywords**.

Supported on RSS (including Reddit sources routed via Lemmy RSS), Google News,
Hacker News, Reddit, GitHub Releases, Podcast, and YouTube collectors.

### RSS / Atom

Any public RSS or Atom feed URL. Most news sites and blogs publish one.

```yaml
feeds:
  - url: "https://www.example.com/rss"
    category: "General News"
    priority: 2
```

### YouTube

Collects the most recent videos from a channel. Requires the channel's `channel_id`
(found on the channel's About page).

Content is sourced using a three-step fallback:

1. **YouTube captions** via `youtube-transcript-api`, free, instant, no download needed.
2. **Whisper transcription** (opt-in), if captions are unavailable, downloads the audio
   with `yt-dlp` and transcribes it via the [OpenRouter Whisper API](#youtube-transcription).
   Requires an OpenRouter API key and `yt-dlp` installed on the server.
3. **RSS description**, falls back to the text the creator wrote in the video description.

```yaml
youtube_channels:
  - handle: "@example"
    channel_id: "UCxxxxxxxxxxxxxxxxxxxxxxxxx"
    category: "Tech"
```

Transient `5xx`/`429` responses from the channel feed are retried automatically.

> **YouTube returning 404/500 on a VPS?** YouTube frequently blocks the channel
> feed (`/feeds/videos.xml`) for datacenter IP ranges, so the same `channel_id`
> that works from your laptop can 404 from a server. Route only the YouTube
> requests through a proxy with the `CONDENSEIT_YOUTUBE_PROXY` environment
> variable (e.g. `CONDENSEIT_YOUTUBE_PROXY=http://user:pass@host:port`). Standard
> `HTTP_PROXY` / `HTTPS_PROXY` variables are also honoured. Other collectors are
> unaffected.

#### YouTube transcription

Audio-based transcription dramatically improves summary quality for videos that
lack captions. Enable and configure it in **Admin > Digest** under the
"YouTube transcription" card, or in `config.yaml`:

```yaml
youtube_transcription:
  enabled: false                          # off by default; enable to activate
  model: "openai/whisper-large-v3-turbo"  # fast and cheap; see below
  max_duration_seconds: 1800              # skip videos longer than 30 min (default)
```

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `false` | Enable audio transcription when captions are unavailable |
| `model` | `openai/whisper-large-v3-turbo` | Whisper model via OpenRouter |
| `max_duration_seconds` | `1800` | Skip videos longer than this (60–7200 s) |

**Available Whisper models on OpenRouter:**

| Model | Speed | Quality | Notes |
|-------|-------|---------|-------|
| `openai/whisper-large-v3-turbo` | Very fast (216× real-time) | Good (12% WER) | Recommended default |
| `openai/whisper-large-v3` | Fast | Best (10.3% WER, 99+ languages) | Use for higher accuracy |

**Cost:** billed per second of audio via your existing OpenRouter key. A typical
15-minute video costs ~$0.036 with `whisper-large-v3-turbo`. Spend is tracked in
**Admin > Budget** alongside summarisation costs and respects your daily/monthly limits.

**Server requirements:** `yt-dlp` and `ffmpeg` must be installed. Both are included
in the Docker images and the VPS provisioning script (`scripts/provision-ubuntu.sh`).
For an existing VPS, install them manually once:

```bash
pip install yt-dlp
apt-get install -y ffmpeg
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

- `llm.provider`: `ollama`, `openrouter`, `fallback` (local then cloud), or `openai`.
- `llm.openrouter_pick_cheapest`: when `true`, the cheapest suitable text model from
  the public OpenRouter catalog is chosen (cached about one hour). You still need
  an API key for requests.
- `llm.openrouter_daily_budget_usd` / `openrouter_monthly_budget_usd`: spend caps.

### OpenAI-compatible endpoint (`provider: "openai"`)

Point CondenseIt at any server that implements the `/v1/chat/completions` endpoint.
This includes Ollama's built-in OpenAI compatibility layer, LM Studio, vLLM,
llama.cpp server, text-generation-inference, real OpenAI, Azure OpenAI, and many
others.

| Setting | Env var | Description |
|---------|---------|-------------|
| `llm.openai_base_url` | `OPENAI_API_BASE_URL` | Full base URL, e.g. `http://localhost:11434/v1` or `https://api.openai.com/v1` |
| `llm.openai_model` | `OPENAI_MODEL` | Model name as the server expects it. Falls back to the top-level `model` field if not set. |
| `llm.openai_api_key` | `OPENAI_API_KEY` | API key. Can be any non-empty string for local servers that don't authenticate. |

Example minimal config for a local vLLM or LM Studio server:

```yaml
llm:
  provider: "openai"
  openai_base_url: "${OPENAI_API_BASE_URL:-http://localhost:8000/v1}"
  openai_model: "gemma4-e4b-q4_m"
```

Set `OPENAI_API_KEY` in `.env` (required if the server enforces authentication; use any placeholder value for servers that don't).

The `openai_base_url` and `openai_model` can also be changed live in **Admin > LLM** without restarting the server.

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
  accept all languages. Language detection uses `langdetect`. This controls
  which articles are *collected*; it does not affect the output language.
- `digest_language` (default `"en"`): language for digest output. Set to an
  ISO 639-1 code (e.g. `"fr"`, `"de"`, `"es"`) to produce summaries in that
  language, or `"source"` to auto-detect each article's language and write the
  summary in the same language as the article. Changeable in **Admin > Settings**
  without restarting the server.
- `youtube_transcription.enabled` (default `false`): enable Whisper audio transcription
  for YouTube videos that lack captions. See [YouTube transcription](#youtube-transcription).

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
| Keyword negative | `keyword_negative` | Penalty for `relevance.disliked_keywords` topics you never want |
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

### Disliked topics

Topics you never want to read about are penalised during scoring and surfaced to
the LLM reranker so they sink. Onboarding writes these to the database
(`bootstrap_dislikes`); you can also list them in `config.yaml`:

```yaml
relevance:
  disliked_keywords: ["crypto", "sports", "celebrity news"]
```

Single words use a substring match; multi-word phrases match only when every
word is present in the title or content (so `celebrity news` penalises an article
containing both words, not just `news`).

### Category balancing gate

Category balancing normally guarantees every category at least one slot to keep
the digest varied. Once you have rated a category enough times, the gate stops
force-feeding categories you consistently dislike. Scores are learned per
category (explicit ratings plus implicit signals) in mean-rating-minus-3 units,
so positive means liked and negative means disliked.

| Setting | Default | Description |
|---------|---------|-------------|
| `relevance.category_exclude_threshold` | `-5.0` | Categories at/below this score are dropped from the digest entirely. Default of −5.0 effectively disables exclusion; raise toward 0 to activate |
| `relevance.category_demote_threshold` | `-5.0` | Categories at/below this score lose their guaranteed slot and are capped at `category_demote_cap`. Default of −5.0 effectively disables demotion; raise toward 0 to activate |
| `relevance.category_demote_cap` | `1` | Max articles a demoted category may keep |
| `relevance.category_min_ratings` | `8` | Minimum explicit ratings a category needs before it can be gated |

The `category_min_ratings` guard means a stated-interest category with only a few
early bad ratings (for example, a couple of 1-star FPV videos) is never buried
before it has a fair chance, it keeps normal behaviour until enough evidence
accumulates. As a safety net, if the gate would remove every article, the top
articles by score are returned so a digest is never silently emptied.

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
| `relevance.embedding_provider` | `"off"` | `"ollama"`, `"openrouter"`, `"openai"`, or `"off"` |
| `relevance.embedding_model` | `"nomic-embed-text"` | Embedding model name |
| `relevance.embedding_preference_weight` | `0.5` | Weight of the embedding signal in the final score |

Recommended models:
- **Ollama (free)**: `nomic-embed-text` - fast, strong quality, requires the model to be pulled once
- **OpenRouter**: `openai/text-embedding-3-small` - $0.02 per million tokens, high quality; a full digest run typically costs under $0.001
- **OpenAI-compatible**: set `embedding_provider: "openai"` to use any server that exposes `/v1/embeddings`. Reuses `llm.openai_base_url` and `llm.openai_api_key`, no extra config needed.

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

**Provider selection**: the reranker follows the same priority order as
summarization, OpenRouter if an API key is present, then OpenAI-compatible
endpoint if `llm.provider: "openai"` and `llm.openai_base_url` is set, then
local Ollama. No separate reranker-provider config is needed.

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

> **Docker users**: the `TZ=UTC` environment variable is set by default in
> `docker-compose.yml` so the container clock matches the default schedule
> timezone. If you change `schedule.timezone`, you may also want to update
> `TZ` in your `docker-compose.yml` to keep log timestamps consistent.

If you prefer external scheduling (cron, systemd, launchd), the
`bash scripts/install.sh` helper can emit ready-to-paste snippets for your
chosen time and cadence (see [installation.md](installation.md)).
