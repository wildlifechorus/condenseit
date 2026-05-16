import { useState, useEffect } from 'preact/hooks';
import { api } from '../lib/api';
import type { PreferenceProfile } from '../lib/types';

/**
 * Collapsible card that shows what the preference engine has learned from
 * your star ratings: liked/disliked terms, category scores, source scores.
 * Only shown in the normal (non-PWA) web app.
 */
export function PreferencesCard() {
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<PreferenceProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Lazy-load the profile the first time the card is expanded. */
  useEffect(() => {
    if (!open || profile !== null) return;
    setLoading(true);
    api
      .getPreferenceProfile()
      .then(setProfile)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load profile.');
      })
      .finally(() => setLoading(false));
  }, [open]);

  const scoreColor = (score: number) =>
    score > 0
      ? 'text-teal-600 dark:text-teal-400'
      : score < 0
        ? 'text-rose-500 dark:text-rose-400'
        : 'text-slate-400 dark:text-slate-500';

  const scorePrefix = (score: number) => (score > 0 ? '+' : '');

  return (
    <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        class="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        <span>Your preferences</span>
        <svg
          class={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div class="px-4 py-4 space-y-4 text-sm">
          {loading && (
            <p class="text-slate-400 dark:text-slate-500">Loading...</p>
          )}
          {error && (
            <p class="text-rose-500 dark:text-rose-400">{error}</p>
          )}
          {profile && !loading && (
            <>
              {/* Learning status */}
              <div class="flex items-center gap-2 flex-wrap">
                <span
                  class={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                    profile.learning_active
                      ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
                  }`}
                >
                  {profile.learning_active ? 'Learning active' : 'Not enough ratings yet'}
                </span>
                <span class="text-xs text-slate-400 dark:text-slate-500">
                  {profile.rating_count} rating{profile.rating_count !== 1 ? 's' : ''}
                  {!profile.learning_active &&
                    ` (need ${profile.min_ratings_threshold})`}
                </span>
              </div>

              {/* Category preferences */}
              {profile.category_preferences.length > 0 && (
                <div>
                  <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                    Categories
                  </p>
                  <ul class="space-y-0.5">
                    {profile.category_preferences.map((c) => (
                      <li key={c.category} class="flex items-center justify-between gap-2">
                        <span class="text-slate-700 dark:text-slate-300 truncate">
                          {c.category}
                        </span>
                        <span class={`font-mono text-xs tabular-nums ${scoreColor(c.score)}`}>
                          {scorePrefix(c.score)}{c.score.toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Source preferences */}
              {profile.source_preferences.length > 0 && (
                <div>
                  <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                    Sources
                  </p>
                  <ul class="space-y-0.5">
                    {profile.source_preferences.map((s) => (
                      <li key={s.source} class="flex items-center justify-between gap-2">
                        <span class="text-slate-700 dark:text-slate-300 truncate text-xs">
                          {s.source}
                        </span>
                        <span class={`font-mono text-xs tabular-nums ${scoreColor(s.score)}`}>
                          {scorePrefix(s.score)}{s.score.toFixed(2)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Top liked terms */}
              {profile.top_liked_terms.length > 0 && (
                <div>
                  <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                    Liked topics
                  </p>
                  <div class="flex flex-wrap gap-1">
                    {profile.top_liked_terms.map((t) => (
                      <span
                        key={t.term}
                        class="px-2 py-0.5 rounded-full text-xs bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300"
                      >
                        {t.term}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Top disliked terms */}
              {profile.top_disliked_terms.length > 0 && (
                <div>
                  <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1">
                    Disliked topics
                  </p>
                  <div class="flex flex-wrap gap-1">
                    {profile.top_disliked_terms.map((t) => (
                      <span
                        key={t.term}
                        class="px-2 py-0.5 rounded-full text-xs bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400"
                      >
                        {t.term}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* No data at all */}
              {profile.category_preferences.length === 0 &&
                profile.source_preferences.length === 0 &&
                profile.top_liked_terms.length === 0 && (
                  <p class="text-xs text-slate-400 dark:text-slate-500">
                    Rate articles on the digest cards to train your preferences.
                  </p>
                )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
