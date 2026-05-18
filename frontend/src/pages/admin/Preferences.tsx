import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { PreferenceProfile } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Spinner } from '../../components/Spinner';

// ---------------------------------------------------------------------------
// Cold-start onboarding panel (Phase 5)
// ---------------------------------------------------------------------------

function BootstrapPanel({
  onSuccess,
}: {
  onSuccess: (summary: string) => void;
}) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    high_keywords: string[];
    medium_keywords: string[];
    profile_summary: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.bootstrapPreferences(text.trim());
      setResult(data);
      onSuccess(data.profile_summary || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Bootstrap failed.');
    } finally {
      setLoading(false);
    }
  }

  if (result) {
    return (
      <Card>
        <CardHeader
          title="Profile seeded"
          description="Your initial preferences have been saved. Run a digest to see them in action."
        />
        {result.profile_summary && (
          <p class="text-sm text-slate-600 dark:text-slate-400 italic mb-3">
            "{result.profile_summary}"
          </p>
        )}
        <div class="flex flex-wrap gap-1.5">
          {result.high_keywords.map((k) => (
            <span
              key={k}
              class="text-xs px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 font-medium"
            >
              {k}
            </span>
          ))}
          {result.medium_keywords.map((k) => (
            <span
              key={k}
              class="text-xs px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
            >
              {k}
            </span>
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Personalise from scratch"
        description="Tell the AI what you care about and it will configure your initial ranking preferences."
      />
      <form onSubmit={handleSubmit} class="space-y-3">
        <textarea
          value={text}
          onInput={(e) => setText((e.target as HTMLTextAreaElement).value)}
          placeholder={
            'e.g. "I care about AI safety, open-source software, and infosec.' +
            ' Not interested in crypto, sports, or celebrity news."'
          }
          rows={4}
          class={[
            'w-full text-sm rounded-lg px-3 py-2 resize-none',
            'border border-slate-200 dark:border-slate-700',
            'bg-white dark:bg-slate-900',
            'text-slate-700 dark:text-slate-300',
            'placeholder-slate-400 dark:placeholder-slate-600',
            'focus:outline-none focus:ring-2 focus:ring-teal-400',
          ].join(' ')}
        />
        {error && (
          <p class="text-xs text-rose-500 dark:text-rose-400">{error}</p>
        )}
        <button
          type="submit"
          disabled={loading || !text.trim()}
          class={[
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium',
            'bg-teal-600 dark:bg-teal-500 text-white',
            'hover:bg-teal-700 dark:hover:bg-teal-400',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors',
          ].join(' ')}
        >
          {loading && <Spinner size="sm" className="text-white" />}
          {loading ? 'Seeding preferences...' : 'Seed my preferences'}
        </button>
      </form>
    </Card>
  );
}

/** Signed score -> CSS color class. */
const scoreColor = (score: number) =>
  score > 0
    ? 'text-teal-600 dark:text-teal-400'
    : score < 0
      ? 'text-rose-500 dark:text-rose-400'
      : 'text-slate-400 dark:text-slate-500';

const scorePrefix = (score: number) => (score > 0 ? '+' : '');

/** Bar representing a signed score clamped to [-2, 2]. */
function ScoreBar({ score, maxAbs = 2 }: { score: number; maxAbs?: number }) {
  const clamped = Math.max(-maxAbs, Math.min(maxAbs, score));
  const pct = Math.abs(clamped) / maxAbs;
  const isPos = clamped >= 0;
  return (
    <div class="flex items-center gap-1.5 flex-1 min-w-0">
      {/* Negative side */}
      <div class="flex-1 flex justify-end">
        {!isPos && (
          <div
            class="h-2 rounded-full bg-rose-400 dark:bg-rose-500"
            style={{ width: `${pct * 100}%` }}
          />
        )}
      </div>
      {/* Centre mark */}
      <div class="w-px h-3 bg-slate-300 dark:bg-slate-600 flex-shrink-0" />
      {/* Positive side */}
      <div class="flex-1">
        {isPos && (
          <div
            class="h-2 rounded-full bg-teal-400 dark:bg-teal-500"
            style={{ width: `${pct * 100}%` }}
          />
        )}
      </div>
    </div>
  );
}

/** Mini bar chart for the rating distribution (1-5 stars). */
function RatingDistribution({
  distribution,
}: {
  distribution: Record<string, number>;
}) {
  const stars = ['1', '2', '3', '4', '5'];
  const max = Math.max(...stars.map((s) => distribution[s] ?? 0), 1);
  const total = stars.reduce((acc, s) => acc + (distribution[s] ?? 0), 0);
  const barColors: Record<string, string> = {
    '1': 'bg-rose-400 dark:bg-rose-500',
    '2': 'bg-orange-400 dark:bg-orange-500',
    '3': 'bg-amber-400 dark:bg-amber-500',
    '4': 'bg-teal-400 dark:bg-teal-500',
    '5': 'bg-emerald-500 dark:bg-emerald-400',
  };
  return (
    <div class="space-y-1.5">
      {stars.map((s) => {
        const count = distribution[s] ?? 0;
        const pct = total > 0 ? (count / max) * 100 : 0;
        return (
          <div key={s} class="flex items-center gap-2">
            <span class="w-4 text-right text-xs text-slate-500 dark:text-slate-400 font-mono flex-shrink-0">
              {s}
            </span>
            <div class="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                class={`h-2 rounded-full transition-all ${barColors[s]}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span class="w-6 text-right text-xs text-slate-400 dark:text-slate-500 font-mono flex-shrink-0">
              {count}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Proportionally sized term badge (size driven by relative weight). */
function TermBadge({
  term,
  score,
  maxScore,
  variant,
}: {
  term: string;
  score: number;
  maxScore: number;
  variant: 'liked' | 'disliked';
}) {
  const relSize = maxScore > 0 ? score / maxScore : 0;
  const fontSize = 10 + relSize * 5; // 10px to 15px
  const baseClass =
    variant === 'liked'
      ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
      : 'bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400';
  return (
    <span
      class={`px-2 py-0.5 rounded-full font-medium ${baseClass}`}
      style={{ fontSize: `${fontSize}px` }}
      title={`Score: ${score.toFixed(2)}`}
    >
      {term}
    </span>
  );
}

export function PreferencesPage() {
  const [profile, setProfile] = useState<PreferenceProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapDone, setBootstrapDone] = useState(false);
  const [showBootstrap, setShowBootstrap] = useState(false);

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
          What the ranking engine has learned from your star ratings and
          engagement signals.
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
                {profile.learning_active
                  ? 'Learning active'
                  : 'Not enough ratings yet'}
              </span>
              <span class="text-sm text-slate-500 dark:text-slate-400">
                {profile.rating_count} explicit rating
                {profile.rating_count !== 1 ? 's' : ''}
                {!profile.learning_active &&
                  ` — need at least ${profile.min_ratings_threshold} to activate`}
              </span>
              {profile.embedding_active && (
                <span class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 font-medium">
                  <span class="w-1.5 h-1.5 rounded-full bg-violet-500" />
                  Semantic profile active
                </span>
              )}
              <button
                type="button"
                onClick={() => setShowBootstrap((v) => !v)}
                class="ml-auto text-xs text-teal-600 dark:text-teal-400 hover:underline"
              >
                {showBootstrap
                  ? 'Hide'
                  : profile.learning_active
                    ? 'Re-seed with AI'
                    : 'Seed with AI'}
              </button>
            </div>
            {!profile.learning_active && (
              <p class="mt-3 text-xs text-slate-400 dark:text-slate-500">
                Star articles on the digest cards to train your ranking
                preferences.
              </p>
            )}
          </Card>

          {/* Cold-start / re-seed panel */}
          {(!profile.learning_active && !bootstrapDone
            ? true
            : showBootstrap) && (
            <BootstrapPanel
              onSuccess={() => {
                setBootstrapDone(true);
                setShowBootstrap(false);
              }}
            />
          )}

          {/* Rating distribution */}
          {profile.rating_count > 0 && (
            <Card>
              <CardHeader title="Rating distribution" />
              <RatingDistribution
                distribution={profile.rating_distribution ?? {}}
              />
            </Card>
          )}

          {/* Implicit signals */}
          <Card>
            <CardHeader
              title="Engagement signals"
              description="Implicit learning from how you interact with articles, beyond star ratings."
            />
            <div class="grid grid-cols-3 gap-3 text-center">
              <div class="space-y-1">
                <p class="text-2xl font-bold text-teal-600 dark:text-teal-400">
                  {profile.implicit_read_count}
                </p>
                <p class="text-xs text-slate-500 dark:text-slate-400">
                  Read
                  <span class="block text-slate-400 dark:text-slate-500">
                    mild positive
                  </span>
                </p>
              </div>
              <div class="space-y-1">
                <p class="text-2xl font-bold text-amber-500 dark:text-amber-400">
                  {profile.implicit_saved_count}
                </p>
                <p class="text-xs text-slate-500 dark:text-slate-400">
                  Saved for later
                  <span class="block text-slate-400 dark:text-slate-500">
                    strong positive
                  </span>
                </p>
              </div>
              <div class="space-y-1">
                <p class="text-2xl font-bold text-rose-500 dark:text-rose-400">
                  {profile.implicit_dismissed_count}
                </p>
                <p class="text-xs text-slate-500 dark:text-slate-400">
                  Dismissed
                  <span class="block text-slate-400 dark:text-slate-500">
                    mild negative
                  </span>
                </p>
              </div>
            </div>
            {!profile.implicit_learning_active && (
              <p class="mt-3 text-xs text-slate-400 dark:text-slate-500">
                Implicit learning is disabled (implicit_signal_weight = 0).
                Enable it under Ranking Weights.
              </p>
            )}
          </Card>

          {/* Time decay info */}
          {profile.rating_count > 0 && profile.earliest_rating && (
            <Card>
              <CardHeader
                title="Time decay"
                description={`Half-life: ${profile.decay_half_life_days} days. Recent ratings carry more weight.`}
              />
              <p class="text-sm text-slate-600 dark:text-slate-400">
                Your oldest rating (
                <span class="font-mono text-xs">
                  {profile.earliest_rating.slice(0, 10)}
                </span>
                ) now carries{' '}
                <span class="font-semibold">
                  {Math.round((profile.oldest_rating_decay ?? 1) * 100)}%
                </span>{' '}
                of its original weight after decay.
              </p>
            </Card>
          )}

          {/* Category preferences */}
          {profile.category_preferences.length > 0 && (
            <Card>
              <CardHeader
                title="Categories"
                description="Score = mean star rating minus 3 (neutral). Positive = liked, negative = disliked."
              />
              <ul class="space-y-2">
                {profile.category_preferences.map((c) => (
                  <li
                    key={c.category}
                    class="flex items-center gap-3 py-1 border-b border-slate-50 dark:border-slate-800 last:border-0"
                  >
                    <span class="text-sm text-slate-700 dark:text-slate-300 w-32 flex-shrink-0 truncate">
                      {c.category}
                    </span>
                    <ScoreBar score={c.score} />
                    <span
                      class={`font-mono text-xs tabular-nums flex-shrink-0 w-12 text-right ${scoreColor(c.score)}`}
                    >
                      {scorePrefix(c.score)}
                      {c.score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Source preferences */}
          {profile.source_preferences.length > 0 && (
            <Card>
              <CardHeader
                title="Sources"
                description="How each feed has performed on average against your ratings."
              />
              <ul class="space-y-2">
                {profile.source_preferences.map((s) => (
                  <li
                    key={s.source}
                    class="flex items-center gap-3 py-1 border-b border-slate-50 dark:border-slate-800 last:border-0"
                  >
                    <span class="text-sm text-slate-600 dark:text-slate-300 w-32 flex-shrink-0 truncate">
                      {s.source}
                    </span>
                    <ScoreBar score={s.score} />
                    <span
                      class={`font-mono text-xs tabular-nums flex-shrink-0 w-12 text-right ${scoreColor(s.score)}`}
                    >
                      {scorePrefix(s.score)}
                      {s.score.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Liked and disliked keyword terms (TF-IDF profile) */}
          {(profile.top_liked_terms.length > 0 ||
            profile.top_disliked_terms.length > 0) && (
            <Card>
              <CardHeader
                title="Content terms"
                description="Keywords and terms extracted from articles you rated. Badge size reflects strength of preference."
              />
              <div class="space-y-4">
                {profile.top_liked_terms.length > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Liked topics
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      {(() => {
                        const maxScore = profile.top_liked_terms[0]?.score ?? 1;
                        return profile.top_liked_terms.map((t) => (
                          <TermBadge
                            key={t.term}
                            term={t.term}
                            score={t.score}
                            maxScore={maxScore}
                            variant="liked"
                          />
                        ));
                      })()}
                    </div>
                  </div>
                )}
                {profile.top_disliked_terms.length > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Disliked topics
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      {(() => {
                        const maxScore =
                          profile.top_disliked_terms[0]?.score ?? 1;
                        return profile.top_disliked_terms.map((t) => (
                          <TermBadge
                            key={t.term}
                            term={t.term}
                            score={t.score}
                            maxScore={maxScore}
                            variant="disliked"
                          />
                        ));
                      })()}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Bigram phrases */}
          {(profile.top_liked_bigrams?.length > 0 ||
            profile.top_disliked_bigrams?.length > 0) && (
            <Card>
              <CardHeader
                title="Keyword phrases"
                description="Two-word phrases from article titles that most influenced ranking."
              />
              <div class="space-y-4">
                {profile.top_liked_bigrams?.length > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Liked phrases
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      {profile.top_liked_bigrams.map((t) => (
                        <span
                          key={t.term}
                          class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300"
                          title={`Score: ${t.score.toFixed(2)}`}
                        >
                          {t.term}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {profile.top_disliked_bigrams?.length > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Disliked phrases
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      {profile.top_disliked_bigrams.map((t) => (
                        <span
                          key={t.term}
                          class="px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400"
                          title={`Score: ${t.score.toFixed(2)}`}
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

          {/* Semantic topics from AI enrichment (Phase 2) */}
          {((profile.top_liked_topics?.length ?? 0) > 0 ||
            (profile.top_disliked_topics?.length ?? 0) > 0) && (
            <Card>
              <CardHeader
                title="AI-extracted topics"
                description="Semantic topics the LLM identified in articles you liked or disliked."
              />
              <div class="space-y-4">
                {(profile.top_liked_topics?.length ?? 0) > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Liked topics
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      {profile.top_liked_topics!.map((t) => (
                        <span
                          key={t.term}
                          class="px-2 py-0.5 rounded-full text-xs font-medium bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300"
                          title={`Score: ${t.score.toFixed(2)}`}
                        >
                          {t.term}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {(profile.top_disliked_topics?.length ?? 0) > 0 && (
                  <div>
                    <p class="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                      Disliked topics
                    </p>
                    <div class="flex flex-wrap gap-1.5">
                      {profile.top_disliked_topics!.map((t) => (
                        <span
                          key={t.term}
                          class="px-2 py-0.5 rounded-full text-xs font-medium bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400"
                          title={`Score: ${t.score.toFixed(2)}`}
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

          {/* No data at all */}
          {profile.category_preferences.length === 0 &&
            profile.source_preferences.length === 0 &&
            profile.top_liked_terms.length === 0 &&
            profile.implicit_read_count === 0 &&
            profile.implicit_saved_count === 0 &&
            profile.implicit_dismissed_count === 0 && (
              <Card>
                <p class="text-sm text-slate-500 dark:text-slate-400 py-2">
                  No preference data yet. Star articles on digest cards or
                  interact with them to start training the ranking engine.
                </p>
              </Card>
            )}
        </>
      )}
    </div>
  );
}
