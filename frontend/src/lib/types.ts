/** All shared TypeScript interfaces for CondenseIt UI. */

export interface DigestItem {
  url: string;
  title: string;
  summary: string;
  source: string;
  category: string;
  kind: string;
  published_at?: string;
  /** Saved star rating (1-5) or null/undefined when not yet rated. */
  rating?: number | null;
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
  html: string;
  items: DigestItem[];
}

export interface Source {
  id: number;
  type: string;
  name: string;
  url: string;
  category: string;
  priority: number;
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
  ollama_host: string;
  ollama_models: string[];
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

export interface AdvisorHardware {
  ram_gb: number;
  gpu_hint: string;
}

export interface AdvisorRecommendation {
  hardware: AdvisorHardware;
  current_model: string;
  recommended_model: string;
  reason: string;
  installed_models: string[];
}

export interface WeeklyRecommendation {
  recommended_model: string;
  reason: string;
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
  top_liked_terms: PreferenceTerm[];
  top_disliked_terms: PreferenceTerm[];
  category_preferences: PreferenceCategoryScore[];
  source_preferences: PreferenceSourceScore[];
}

export interface Benchmark {
  model: string;
  elapsed_s: number;
  tokens_per_sec: number;
  run_at: string;
}

export interface AdminOverview {
  source_count: number;
  provider: string;
  model: string;
  latest?: DigestEntry;
}

export interface AdvisorPageData {
  recommendation: AdvisorRecommendation;
  weekly: WeeklyRecommendation | null;
  benchmarks: Benchmark[];
}
