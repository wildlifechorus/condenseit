import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { PreferenceProfile } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Spinner } from '../../components/Spinner';

const scoreColor = (score: number) =>
  score > 0
    ? 'text-teal-600 dark:text-teal-400'
    : score < 0
      ? 'text-rose-500 dark:text-rose-400'
      : 'text-slate-400 dark:text-slate-500';

const scorePrefix = (score: number) => (score > 0 ? '+' : '');

export function PreferencesPage() {
  const [profile, setProfile] = useState<PreferenceProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getPreferenceProfile()
      .then(setProfile)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load profile.');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Learning profile
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          What the ranking engine has learned from your star ratings. Read-only.
        </p>
      </div>

      {error && (
        <div class="px-4 py-3 text-sm rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800">
          {error}
        </div>
      )}

      {profile && (
        <>
          {/* Learning status */}
          <Card>
            <div class="flex items-center gap-3 flex-wrap">
              <span
                class={[
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
                  profile.learning_active
                    ? 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400',
                ].join(' ')}
              >
                <span
                  class={[
                    'w-1.5 h-1.5 rounded-full',
                    profile.learning_active ? 'bg-teal-500' : 'bg-slate-400',
                  ].join(' ')}
                />
                {profile.learning_active ? 'Learning active' : 'Not enough ratings yet'}
              </span>
              <span class="text-sm text-slate-500 dark:text-slate-400">
                {profile.rating_count} rating{profile.rating_count !== 1 ? 's' : ''}
                {!profile.learning_active &&
                  ` — need at least ${profile.min_ratings_threshold} to activate`}
              </span>
            </div>
            {!profile.learning_active && (
              <p class="mt-3 text-xs text-slate-400 dark:text-slate-500">
                Star articles on the digest cards to train your ranking preferences.
              </p>
            )}
          </Card>

          {/* Category preferences */}
          {profile.category_preferences.length > 0 && (
            <Card>
              <CardHeader title="Categories" />
              <ul class="space-y-1">
                {profile.category_preferences.map((c) => (
                  <li
                    key={c.category}
                    class="flex items-center justify-between gap-4 py-1 border-b border-slate-50 dark:border-slate-800 last:border-0"
                  >
                    <span class="text-sm text-slate-700 dark:text-slate-300 truncate">
                      {c.category}
                    </span>
                    <span
                      class={`font-mono text-xs tabular-nums flex-shrink-0 ${scoreColor(c.score)}`}
                    >
                      {scorePrefix(c.score)}{c.score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Source preferences */}
          {profile.source_preferences.length > 0 && (
            <Card>
              <CardHeader title="Sources" />
              <ul class="space-y-1">
                {profile.source_preferences.map((s) => (
                  <li
                    key={s.source}
                    class="flex items-center justify-between gap-4 py-1 border-b border-slate-50 dark:border-slate-800 last:border-0"
                  >
                    <span class="text-sm text-slate-600 dark:text-slate-300 truncate">
                      {s.source}
                    </span>
                    <span
                      class={`font-mono text-xs tabular-nums flex-shrink-0 ${scoreColor(s.score)}`}
                    >
                      {scorePrefix(s.score)}{s.score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Liked and disliked topics */}
          {(profile.top_liked_terms.length > 0 ||
            profile.top_disliked_terms.length > 0) && (
            <Card>
              <CardHeader title="Topics" />
              <div class="space-y-4">
                {profile.top_liked_terms.length > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Liked
                    </p>
                    <div class="flex flex-wrap gap-1.5">
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
                {profile.top_disliked_terms.length > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Disliked
                    </p>
                    <div class="flex flex-wrap gap-1.5">
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
              </div>
            </Card>
          )}

          {/* No data */}
          {profile.category_preferences.length === 0 &&
            profile.source_preferences.length === 0 &&
            profile.top_liked_terms.length === 0 && (
              <Card>
                <p class="text-sm text-slate-500 dark:text-slate-400 py-2">
                  No preference data yet. Star articles on digest cards to start
                  training the ranking engine.
                </p>
              </Card>
            )}
        </>
      )}
    </div>
  );
}
