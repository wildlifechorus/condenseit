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
  /** Number of articles currently saved for later (implicit strong positive). */
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
}

export interface RankingWeights {
  tfidf_preference_weight: number;
  category_preference_weight: number;
  source_preference_weight: number;
  implicit_signal_weight: number;
  rating_decay_half_life_days: number;
  min_ratings_for_learning: number;
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
}

export interface ScheduleConfig {
  times: string[];
  enabled: boolean;
  next_run_utc: string | null;
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

// ---------- Read Later ---------------------------------------------------

/**
 * A digest item that the user has saved to the read-later list.
 * Mirrors DigestItem plus a `saved_at` timestamp set when it was bookmarked.
 */
export interface ReadLaterItem extends DigestItem {
  saved_at: string;
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
