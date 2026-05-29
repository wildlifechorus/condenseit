/** All shared TypeScript interfaces for CondenseIt UI. */

/**
 * Per-signal breakdown of how an article's preference_score was composed.
 * All values are signed floats (positive = good, negative = penalised).
 */
export interface ScoreBreakdown {
  keyword_high: number;
  keyword_medium: number;
  term_overlap: number;
  bigram_overlap: number;
  tfidf_cosine: number;
  category: number;
  source: number;
  implicit_content: number;
  implicit_category: number;
  implicit_source: number;
  synonym_boost: number;
  /** Phase 1: cosine similarity to the decay-weighted embedding centroid. */
  embedding_similarity: number;
  /** Phase 2: overlap with LLM-extracted topic profile. */
  topic_score: number;
  /** Phase 3: blended score component from the LLM reranker. */
  llm_rerank: number;
  /** Phase 3: human-readable reason from the LLM reranker (may be absent). */
  llm_reason?: string;
}

export interface DigestItem {
  url: string;
  title: string;
  summary: string;
  /** One-sentence summary produced by the LLM structured output. */
  tldr?: string;
  /** Bullet-point takeaways produced by the LLM structured output. */
  key_takeaways?: string[];
  source: string;
  category: string;
  kind: string;
  published_at?: string;
  /** Saved star rating (1-5) or null/undefined when not yet rated. */
  rating?: number | null;
  /** OG or media thumbnail URL extracted during collection, if available. */
  image_url?: string;
  /** Total preference score used for ranking (higher = ranked higher). */
  preference_score?: number;
  /** Per-signal breakdown of the preference_score. */
  score_breakdown?: ScoreBreakdown;
  /** Phase 2: LLM-extracted semantic topics (kebab-case). */
  topics?: string[];
  /** Phase 2: Named entities (people, orgs, products) mentioned. */
  entities?: string[];
  /** Phase 2: Novelty score 1-5 (how surprising vs mainstream). */
  novelty?: number;
  /** Phase 4: One-sentence relevance note for this reader. */
  relevance_to_you?: string;
  /** True when the article matched a per-source highlight keyword rule. */
  highlighted?: boolean;
}

export interface DigestEntry {
  id: number;
  created_at: string;
}

export interface DigestMeta {
  id: number;
  created_at: string;
  articles_count?: number;
  model?: string;
  processing_time?: string;
}

export interface DigestDetail {
  meta: DigestMeta;
  items: DigestItem[];
}

export interface Source {
  id: number;
  type: string;
  name: string;
  url: string;
  category: string;
  priority: number;
  /** 1 = enabled, 0 = disabled. Defaults to 1 for newly-added sources. */
  enabled: number;
  /** Type-specific source settings stored by the backend as JSON text. */
  extra_json?: string;
  last_status?: string;
  last_item_count?: number;
  last_checked_at?: string;
  last_error?: string;
}

export interface RatingArticle {
  url: string;
  title: string;
  category: string;
  rating?: number | null;
}

export interface LlmConfig {
  provider: string;
  model: string;
  openrouter_model: string;
  openrouter_pick_cheapest: boolean;
  /** Resolved cheapest model when pick_cheapest is enabled. */
  cheapest_model_id?: string;
  ollama_host: string;
  ollama_models: string[];
  ollama_reachable: boolean;
}

export interface ApiKey {
  service: string;
  key_preview: string;
}

export type JobState = 'idle' | 'running' | 'completed' | 'failed';

export interface Job {
  state: JobState;
  message: string;
  digest_id?: number;
  post_display?: string;
}

export interface PreferenceTerm {
  term: string;
  score: number;
}

export interface PreferenceCategoryScore {
  category: string;
  score: number;
}

export interface PreferenceSourceScore {
  source: string;
  score: number;
}

export interface PreferenceProfile {
  rating_count: number;
  earliest_rating: string;
  latest_rating: string;
  min_ratings_threshold: number;
  learning_active: boolean;
  /** Distribution of star ratings: keys are '1'-'5', values are counts. */
  rating_distribution: Record<string, number>;
  /** Number of articles that were marked as read (implicit positive signal). */
  implicit_read_count: number;
  /** Number of articles ever saved for later, including processed ones (implicit strong positive). */
  implicit_saved_count: number;
  /** Number of articles the user has dismissed (implicit negative signal). */
  implicit_dismissed_count: number;
  /** Whether implicit learning is active (implicit_signal_weight > 0). */
  implicit_learning_active: boolean;
  /** How much weight the oldest rating carries after decay (0-1). */
  oldest_rating_decay: number;
  /** Decay half-life in days used for this profile. */
  decay_half_life_days: number;
  top_liked_terms: PreferenceTerm[];
  top_disliked_terms: PreferenceTerm[];
  top_liked_bigrams: PreferenceTerm[];
  top_disliked_bigrams: PreferenceTerm[];
  category_preferences: PreferenceCategoryScore[];
  source_preferences: PreferenceSourceScore[];
  /** Phase 1: true when an embedding profile centroid has been built. */
  embedding_active?: boolean;
  /** Phase 2: top semantic topics extracted from liked articles. */
  top_liked_topics?: PreferenceTerm[];
  /** Phase 2: top semantic topics extracted from disliked articles. */
  top_disliked_topics?: PreferenceTerm[];
}

export interface RankingWeights {
  tfidf_preference_weight: number;
  category_preference_weight: number;
  source_preference_weight: number;
  implicit_signal_weight: number;
  rating_decay_half_life_days: number;
  min_ratings_for_learning: number;
  /** Phase 1: weight of the embedding cosine-similarity signal. */
  embedding_preference_weight: number;
  /** Phase 1: embedding provider selection. */
  embedding_provider: 'off' | 'ollama' | 'openrouter';
  /** Phase 1: model used to generate embeddings. */
  embedding_model: string;
  /** Phase 2: weight of the LLM topic overlap signal. */
  topic_score_weight: number;
  /** Phase 3: enable LLM reranker pass. */
  llm_rerank_enabled: boolean;
  /** Phase 3: model used for reranking (empty = use summarizer model). */
  llm_rerank_model: string;
  /** Phase 3: number of top candidates sent to the reranker. */
  llm_rerank_top_k: number;
  /** Phase 3: blend weight between LLM score and classical score (0-1). */
  llm_rerank_blend: number;
  /** Semantic dedup: use embeddings to collapse same-story articles. Only active when embedding_provider != "off". */
  semantic_dedup_enabled: boolean;
  /** Cosine similarity threshold above which two articles are treated as the same story (0.5-1.0). */
  semantic_dedup_threshold: number;
}

// ---------- Budget -------------------------------------------------------

export interface OpenRouterUsage {
  usage_daily: number;
  usage_weekly: number;
  usage_monthly: number;
  limit: number | null;
  limit_remaining: number | null;
  is_free_tier: boolean;
}

export interface ModelSpend {
  model: string;
  total_usd: number;
  requests: number;
}

export interface DigestCost {
  digest_id: number;
  created_at: string;
  cost_usd: number;
  articles: number;
}

export interface LocalBudget {
  today_usd: number;
  month_usd: number;
  daily_limit_usd: number;
  monthly_limit_usd: number;
  /** Average LLM cost per digest run across all time. */
  avg_cost_per_digest_usd: number;
  by_model: ModelSpend[];
  recent_digests: DigestCost[];
}

export interface BudgetData {
  /** Present when provider is openrouter and API key is set. */
  openrouter: OpenRouterUsage | null;
  local: LocalBudget;
}

// ---------- Scheduler ----------------------------------------------------

export interface SchedulerStatus {
  enabled: boolean;
  next_run_utc: string | null;
  schedule_times: string[];
  timezone: string;
}

export interface ScheduleConfig {
  times: string[];
  enabled: boolean;
  next_run_utc: string | null;
  timezone: string;
}

// ---------- Digest settings ----------------------------------------------

export interface DigestConfig {
  max_articles_per_digest: number;
  balance_digest_categories: boolean;
  max_articles_per_category: number;
  max_article_age_hours: number;
  preferred_languages: string[];
  exclude_keywords: string[];
  max_key_takeaways: number;
  max_summary_paragraphs: number;
  youtube_transcription_enabled: boolean;
  youtube_transcription_model: string;
  youtube_transcription_max_duration: number;
}

// ---------- Budget limits ------------------------------------------------

export interface BudgetLimits {
  daily_budget_usd: number;
  monthly_budget_usd: number;
}

// ---------- Password / security ------------------------------------------

export interface PasswordInfo {
  /** 'default' | 'env' | 'db' */
  source: string;
  using_default: boolean;
}

export interface FeedTokenInfo {
  exists: boolean;
  token: string | null;
  feed_url: string | null;
}

// ---------- Read Later ---------------------------------------------------

/**
 * A digest item that the user has saved to the read-later list.
 * Mirrors DigestItem plus a `saved_at` timestamp set when it was bookmarked.
 */
export interface ReadLaterItem extends DigestItem {
  saved_at: string;
}

// ---------- Starred ------------------------------------------------------

/**
 * A digest item the user has starred for permanent keeping.
 * Mirrors DigestItem plus a `starred_at` timestamp set when it was starred.
 */
export interface StarredItem extends DigestItem {
  starred_at: string;
}

// ---------- Run logs -----------------------------------------------------

export interface RunLogSummary {
  id: number;
  digest_id: number | null;
  created_at: string;
  log_preview: string;
}

export interface RunLog {
  id: number;
  digest_id: number | null;
  created_at: string;
  log_text: string;
}
