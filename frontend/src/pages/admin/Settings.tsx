import { useState, useEffect, useRef } from 'preact/hooks';
import { api } from '../../lib/api';
import type { DigestConfig, RankingWeights } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Button } from '../../components/Button';
import { Spinner } from '../../components/Spinner';

const INPUT =
  'w-full px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: preact.ComponentChildren;
}) {
  return (
    <label class="flex flex-col gap-1">
      <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </span>
      {children}
      {hint && (
        <span class="text-xs text-slate-400 dark:text-slate-500">{hint}</span>
      )}
    </label>
  );
}

/** Simple tag-style language input. */
function LanguageInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (langs: string[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');

  function addLang(raw: string) {
    const code = raw.trim().toLowerCase().slice(0, 5);
    if (!code) return;
    if (!value.includes(code)) {
      onChange([...value, code]);
    }
    setDraft('');
    if (inputRef.current) inputRef.current.value = '';
  }

  function removeLang(code: string) {
    onChange(value.filter((l) => l !== code));
  }

  function handleKeyDown(e: KeyboardEvent) {
    const target = e.target as HTMLInputElement;
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addLang(target.value);
    } else if (e.key === 'Backspace' && !target.value && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div class="flex flex-wrap gap-1.5 p-2 min-h-[42px] bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg focus-within:ring-2 focus-within:ring-teal-500">
      {value.map((code) => (
        <span
          key={code}
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-teal-100 dark:bg-teal-900/40 text-teal-800 dark:text-teal-200"
        >
          {code}
          <button
            type="button"
            onClick={() => removeLang(code)}
            class="hover:text-red-500 dark:hover:text-red-400 transition-colors leading-none"
            aria-label={`Remove ${code}`}
          >
            x
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        class="flex-1 min-w-[80px] bg-transparent text-sm text-slate-900 dark:text-slate-100 focus:outline-none placeholder:text-slate-400"
        placeholder={value.length === 0 ? 'en, pt, de...' : ''}
        value={draft}
        onInput={(e) => setDraft((e.target as HTMLInputElement).value)}
        onKeyDown={handleKeyDown}
        onBlur={(e) => addLang((e.target as HTMLInputElement).value)}
      />
    </div>
  );
}

/** Generic tag-style input for arbitrary keyword phrases. */
function KeywordInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (keywords: string[]) => void;
  placeholder?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');

  function addKeyword(raw: string) {
    const phrase = raw.trim();
    if (!phrase) return;
    if (!value.includes(phrase)) {
      onChange([...value, phrase]);
    }
    setDraft('');
    if (inputRef.current) inputRef.current.value = '';
  }

  function removeKeyword(phrase: string) {
    onChange(value.filter((k) => k !== phrase));
  }

  function handleKeyDown(e: KeyboardEvent) {
    const target = e.target as HTMLInputElement;
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addKeyword(target.value);
    } else if (e.key === 'Backspace' && !target.value && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div class="flex flex-wrap gap-1.5 p-2 min-h-[42px] bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg focus-within:ring-2 focus-within:ring-teal-500">
      {value.map((phrase) => (
        <span
          key={phrase}
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-200"
        >
          {phrase}
          <button
            type="button"
            onClick={() => removeKeyword(phrase)}
            class="hover:text-red-500 dark:hover:text-red-400 transition-colors leading-none"
            aria-label={`Remove ${phrase}`}
          >
            x
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        type="text"
        class="flex-1 min-w-[120px] bg-transparent text-sm text-slate-900 dark:text-slate-100 focus:outline-none placeholder:text-slate-400"
        placeholder={
          value.length === 0
            ? (placeholder ?? 'Community Forum, sponsored...')
            : ''
        }
        value={draft}
        onInput={(e) => setDraft((e.target as HTMLInputElement).value)}
        onKeyDown={handleKeyDown}
        onBlur={(e) => addKeyword((e.target as HTMLInputElement).value)}
      />
    </div>
  );
}

export function SettingsPage() {
  const [cfg, setCfg] = useState<DigestConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<{ text: string; ok: boolean } | null>(
    null,
  );

  const [weights, setWeights] = useState<RankingWeights | null>(null);
  const [savingWeights, setSavingWeights] = useState(false);

  useEffect(() => {
    api
      .getDigestConfig()
      .then(setCfg)
      .catch((e: unknown) => {
        showFlash(
          e instanceof Error ? e.message : 'Failed to load settings.',
          false,
        );
      })
      .finally(() => setLoading(false));

    api
      .getRankingWeights()
      .then(setWeights)
      .catch(() => undefined);
  }, []);

  function showFlash(text: string, ok = true) {
    setFlash({ text, ok });
    setTimeout(() => setFlash(null), 4000);
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    if (!cfg) return;
    setSaving(true);
    try {
      await api.saveDigestConfig(cfg);
      showFlash('Settings saved.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Save failed.', false);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveWeights(e: Event) {
    e.preventDefault();
    if (!weights) return;
    setSavingWeights(true);
    try {
      await api.saveRankingWeights(weights);
      showFlash('Ranking weights saved.');
    } catch (err) {
      showFlash(
        err instanceof Error ? err.message : 'Failed to save weights.',
        false,
      );
    } finally {
      setSavingWeights(false);
    }
  }

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  if (!cfg) {
    return (
      <p class="text-sm text-red-600 dark:text-red-400 p-4">
        {flash?.text ?? 'Could not load settings.'}
      </p>
    );
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Digest settings
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Article limits, language filter, and summary format.
        </p>
      </div>

      {flash && (
        <div
          class={[
            'px-4 py-3 text-sm rounded-lg border',
            flash.ok
              ? 'bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800'
              : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
          ].join(' ')}
        >
          {flash.text}
        </div>
      )}

      <form onSubmit={handleSave} class="space-y-5">
        <Card>
          <CardHeader title="Digest limits" />
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label="Max articles per digest"
              hint="Total articles included in each digest run (1-200)."
            >
              <input
                type="number"
                class={INPUT}
                min={1}
                max={200}
                required
                value={cfg.max_articles_per_digest}
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          max_articles_per_digest: parseInt(
                            (e.target as HTMLInputElement).value,
                            10,
                          ) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <Field
              label="Max articles per category"
              hint="Cap per category when balancing is enabled (1-50)."
            >
              <input
                type="number"
                class={INPUT}
                min={1}
                max={50}
                required
                value={cfg.max_articles_per_category}
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          max_articles_per_category: parseInt(
                            (e.target as HTMLInputElement).value,
                            10,
                          ) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <Field
              label="Age filter cutoff"
              hint={
                'Exclude articles older than this many hours. Set to 0 to disable.'
              }
            >
              <input
                type="number"
                class={INPUT}
                min={0}
                required
                value={cfg.max_article_age_hours}
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          max_article_age_hours: parseInt(
                            (e.target as HTMLInputElement).value,
                            10,
                          ) || 0,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <div class="sm:col-span-2">
              <label class="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  class="mt-0.5"
                  checked={cfg.balance_digest_categories}
                  onChange={(e) =>
                    setCfg((p) =>
                      p
                        ? {
                            ...p,
                            balance_digest_categories: (
                              e.target as HTMLInputElement
                            ).checked,
                          }
                        : p,
                    )
                  }
                />
                <span class="text-sm text-slate-700 dark:text-slate-300">
                  Balance categories (reserve one slot per category before filling by rank)
                </span>
              </label>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Summary format" />
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label="Key takeaways per article"
              hint="Number of bullet points the LLM produces per article (1-10)."
            >
              <input
                type="number"
                class={INPUT}
                min={1}
                max={10}
                required
                value={cfg.max_key_takeaways}
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          max_key_takeaways: parseInt(
                            (e.target as HTMLInputElement).value,
                            10,
                          ) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <Field
              label="Summary paragraphs per article"
              hint="Number of paragraphs in each article summary (1-10)."
            >
              <input
                type="number"
                class={INPUT}
                min={1}
                max={10}
                required
                value={cfg.max_summary_paragraphs}
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          max_summary_paragraphs: parseInt(
                            (e.target as HTMLInputElement).value,
                            10,
                          ) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Language preferences"
            description="Only include articles in these languages. Leave empty to accept all languages."
          />
          <Field
            label="Preferred languages"
            hint="Type an ISO 639-1 code (e.g. en, pt, de) and press Enter or comma to add. Leave empty for no filter."
          >
            <LanguageInput
              value={cfg.preferred_languages}
              onChange={(langs) =>
                setCfg((p) => (p ? { ...p, preferred_languages: langs } : p))
              }
            />
          </Field>
        </Card>

        <Card>
          <CardHeader
            title="Keyword exclusions"
            description="Articles whose title or description contains any of these phrases are dropped before ranking. Matching is case-insensitive."
          />
          <Field
            label="Excluded keywords"
            hint="Type a phrase and press Enter or comma to add. Leave empty to disable."
          >
            <KeywordInput
              value={cfg.exclude_keywords}
              onChange={(keywords) =>
                setCfg((p) =>
                  p ? { ...p, exclude_keywords: keywords } : p,
                )
              }
            />
          </Field>
        </Card>

        <Card>
          <CardHeader
            title="YouTube transcription"
            description="When enabled, videos without captions are transcribed via OpenRouter Whisper. Requires an OpenRouter API key and yt-dlp installed on the server."
          />
          <div class="space-y-4">
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                class="mt-0.5"
                checked={cfg.youtube_transcription_enabled}
                onChange={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          youtube_transcription_enabled: (
                            e.target as HTMLInputElement
                          ).checked,
                        }
                      : p,
                  )
                }
              />
              <span class="text-sm text-slate-700 dark:text-slate-300">
                Enable audio transcription for YouTube videos (uses OpenRouter
                Whisper API, billed per second of audio)
              </span>
            </label>

            {cfg.youtube_transcription_enabled && (
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field
                  label="Whisper model"
                  hint="openai/whisper-large-v3-turbo is fast and cheap. openai/whisper-large-v3 is highest quality."
                >
                  <select
                    class={INPUT}
                    value={cfg.youtube_transcription_model}
                    onChange={(e) =>
                      setCfg((p) =>
                        p
                          ? {
                              ...p,
                              youtube_transcription_model: (
                                e.target as HTMLSelectElement
                              ).value,
                            }
                          : p,
                      )
                    }
                  >
                    <option value="openai/whisper-large-v3-turbo">
                      whisper-large-v3-turbo (fast, cheap)
                    </option>
                    <option value="openai/whisper-large-v3">
                      whisper-large-v3 (best quality)
                    </option>
                  </select>
                </Field>

                <Field
                  label="Max video duration (seconds)"
                  hint="Videos longer than this are skipped. Default 1800 (30 min). Max 7200 (2 hours)."
                >
                  <input
                    type="number"
                    class={INPUT}
                    min={60}
                    max={7200}
                    required
                    value={cfg.youtube_transcription_max_duration}
                    onInput={(e) =>
                      setCfg((p) =>
                        p
                          ? {
                              ...p,
                              youtube_transcription_max_duration:
                                parseInt(
                                  (e.target as HTMLInputElement).value,
                                  10,
                                ) || 1800,
                            }
                          : p,
                      )
                    }
                  />
                </Field>
              </div>
            )}
          </div>
        </Card>

        <div>
          <Button type="submit" loading={saving}>
            Save settings
          </Button>
        </div>
      </form>

      {weights && (
        <form onSubmit={handleSaveWeights} class="space-y-5 mt-8">
          <div>
            <h2 class="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              Ranking weights
            </h2>
            <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Fine-tune how the preference engine blends signals when ordering
              articles. Changes take effect on the next digest run.
            </p>
          </div>

          <Card>
            <CardHeader
              title="Explicit ratings"
              description="Weights applied to signals derived from your star ratings."
            />
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field
                label="TF-IDF content weight"
                hint="How much term-level content similarity influences ranking (0 = off, 1 = strong)."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={0}
                  max={5}
                  step={0.05}
                  required
                  value={weights.tfidf_preference_weight}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            tfidf_preference_weight:
                              parseFloat(
                                (e.target as HTMLInputElement).value,
                              ) || 0,
                          }
                        : w,
                    )
                  }
                />
              </Field>

              <Field
                label="Category weight"
                hint="Influence of per-category mean rating deviation (0 = off)."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={0}
                  max={5}
                  step={0.05}
                  required
                  value={weights.category_preference_weight}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            category_preference_weight:
                              parseFloat(
                                (e.target as HTMLInputElement).value,
                              ) || 0,
                          }
                        : w,
                    )
                  }
                />
              </Field>

              <Field
                label="Source weight"
                hint="Influence of per-feed/source mean rating deviation (0 = off)."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={0}
                  max={5}
                  step={0.05}
                  required
                  value={weights.source_preference_weight}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            source_preference_weight:
                              parseFloat(
                                (e.target as HTMLInputElement).value,
                              ) || 0,
                          }
                        : w,
                    )
                  }
                />
              </Field>

              <Field
                label="Min ratings to activate"
                hint="Number of star ratings needed before the engine starts learning."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={1}
                  max={1000}
                  required
                  value={weights.min_ratings_for_learning}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            min_ratings_for_learning:
                              parseInt(
                                (e.target as HTMLInputElement).value,
                                10,
                              ) || 1,
                          }
                        : w,
                    )
                  }
                />
              </Field>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Implicit signals"
              description="How much engagement signals (read, saved, dismissed) influence ranking relative to explicit ratings."
            />
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field
                label="Implicit signal weight"
                hint="0 = disabled; 0.5 = half the influence of explicit ratings; 1.0 = equal influence."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={0}
                  max={1}
                  step={0.05}
                  required
                  value={weights.implicit_signal_weight}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            implicit_signal_weight:
                              parseFloat(
                                (e.target as HTMLInputElement).value,
                              ) || 0,
                          }
                        : w,
                    )
                  }
                />
              </Field>

              <Field
                label="Decay half-life (days)"
                hint="Older ratings count less. After this many days a rating is worth half as much."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={1}
                  max={3650}
                  required
                  value={weights.rating_decay_half_life_days}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            rating_decay_half_life_days:
                              parseInt(
                                (e.target as HTMLInputElement).value,
                                10,
                              ) || 30,
                          }
                        : w,
                    )
                  }
                />
              </Field>
            </div>
          </Card>

          {/* ---- AI Ranking ---- */}
          <div class="pt-2">
            <h3 class="text-base font-semibold text-slate-900 dark:text-slate-100">
              AI ranking
            </h3>
            <p class="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
              Optional AI layers on top of classical ranking. Each feature is
              independent and off by default.
            </p>
          </div>

          <Card>
            <CardHeader
              title="Semantic embeddings"
              description="Encode articles as vectors and score them against a centroid built from your liked content. Embeddings are cached in SQLite after the first run."
            />
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field
                label="Embedding provider"
                hint="off = disabled. ollama = free local. openrouter = cloud (fractions of a cent per run)."
              >
                <select
                  class={INPUT}
                  value={weights.embedding_provider}
                  onChange={(e) => {
                    const provider = (e.target as HTMLSelectElement)
                      .value as 'off' | 'ollama' | 'openrouter';
                    const defaultModel =
                      provider === 'ollama'
                        ? 'nomic-embed-text'
                        : provider === 'openrouter'
                          ? 'openai/text-embedding-3-small'
                          : '';
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            embedding_provider: provider,
                            embedding_model:
                              w.embedding_model &&
                              w.embedding_model !== 'nomic-embed-text' &&
                              w.embedding_model !==
                                'openai/text-embedding-3-small'
                                ? w.embedding_model
                                : defaultModel,
                          }
                        : w,
                    );
                  }}
                >
                  <option value="off">off</option>
                  <option value="ollama">ollama</option>
                  <option value="openrouter">openrouter</option>
                </select>
              </Field>

              {weights.embedding_provider !== 'off' && (
                <Field
                  label="Embedding model"
                  hint={
                    weights.embedding_provider === 'openrouter'
                      ? 'openai/text-embedding-3-small is cheapest ($0.02/1M tokens, high quality).'
                      : 'nomic-embed-text is free and works well for news content.'
                  }
                >
                  <input
                    type="text"
                    class={INPUT}
                    value={weights.embedding_model}
                    placeholder={
                      weights.embedding_provider === 'openrouter'
                        ? 'openai/text-embedding-3-small'
                        : 'nomic-embed-text'
                    }
                    onInput={(e) =>
                      setWeights((w) =>
                        w
                          ? {
                              ...w,
                              embedding_model: (e.target as HTMLInputElement)
                                .value,
                            }
                          : w,
                      )
                    }
                  />
                </Field>
              )}

              {weights.embedding_provider !== 'off' && (
                <Field
                  label="Embedding similarity weight"
                  hint="How strongly the embedding cosine similarity score influences ranking (0 = off)."
                >
                  <input
                    type="number"
                    class={INPUT}
                    min={0}
                    max={5}
                    step={0.05}
                    value={weights.embedding_preference_weight}
                    onInput={(e) =>
                      setWeights((w) =>
                        w
                          ? {
                              ...w,
                              embedding_preference_weight:
                                parseFloat(
                                  (e.target as HTMLInputElement).value,
                                ) || 0,
                            }
                          : w,
                      )
                    }
                  />
                </Field>
              )}

              {weights.embedding_provider !== 'off' && (
                <div class="sm:col-span-2 space-y-3">
                  <label class="flex items-start gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      class="mt-0.5"
                      checked={weights.semantic_dedup_enabled}
                      onChange={(e) =>
                        setWeights((w) =>
                          w
                            ? {
                                ...w,
                                semantic_dedup_enabled: (
                                  e.target as HTMLInputElement
                                ).checked,
                              }
                            : w,
                        )
                      }
                    />
                    <span class="text-sm text-slate-700 dark:text-slate-300">
                      Deduplicate same-story articles using embeddings
                    </span>
                  </label>

                  {weights.semantic_dedup_enabled && (
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 pl-6">
                      <Field
                        label="Duplicate similarity threshold"
                        hint="Cosine similarity above which two articles are treated as the same story. 0.85 is recommended; lower = more aggressive (0.80), higher = more conservative (0.90)."
                      >
                        <input
                          type="number"
                          class={INPUT}
                          min={0.5}
                          max={1.0}
                          step={0.01}
                          value={weights.semantic_dedup_threshold}
                          onInput={(e) =>
                            setWeights((w) =>
                              w
                                ? {
                                    ...w,
                                    semantic_dedup_threshold:
                                      parseFloat(
                                        (e.target as HTMLInputElement).value,
                                      ) || 0.85,
                                  }
                                : w,
                            )
                          }
                        />
                      </Field>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Topic enrichment"
              description="The LLM extracts topics, entities, and a novelty score from each article during summarisation (no extra calls). These feed a topic preference profile built from your ratings."
            />
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field
                label="Topic score weight"
                hint="How much the topic-profile overlap score influences ranking (0 = off). Requires at least one summarised and rated article."
              >
                <input
                  type="number"
                  class={INPUT}
                  min={0}
                  max={5}
                  step={0.05}
                  value={weights.topic_score_weight}
                  onInput={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            topic_score_weight:
                              parseFloat(
                                (e.target as HTMLInputElement).value,
                              ) || 0,
                          }
                        : w,
                    )
                  }
                />
              </Field>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="LLM reranker"
              description="After classical scoring, send the top-K candidates to an LLM with a compact reader profile. The LLM score is blended with the classical score. One call per digest run."
            />
            <div class="space-y-4">
              <label class="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  class="mt-0.5"
                  checked={weights.llm_rerank_enabled}
                  onChange={(e) =>
                    setWeights((w) =>
                      w
                        ? {
                            ...w,
                            llm_rerank_enabled: (e.target as HTMLInputElement)
                              .checked,
                          }
                        : w,
                    )
                  }
                />
                <span class="text-sm text-slate-700 dark:text-slate-300">
                  Enable LLM reranker
                </span>
              </label>

              {weights.llm_rerank_enabled && (
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field
                    label="Reranker model"
                    hint="Leave blank to use the same model as the summariser. Cheap models work well here (e.g. deepseek/deepseek-v3)."
                  >
                    <input
                      type="text"
                      class={INPUT}
                      value={weights.llm_rerank_model}
                      placeholder="(same as summariser)"
                      onInput={(e) =>
                        setWeights((w) =>
                          w
                            ? {
                                ...w,
                                llm_rerank_model: (
                                  e.target as HTMLInputElement
                                ).value,
                              }
                            : w,
                        )
                      }
                    />
                  </Field>

                  <Field
                    label="Top-K candidates"
                    hint="Number of top-ranked articles sent to the LLM for reordering (1-200)."
                  >
                    <input
                      type="number"
                      class={INPUT}
                      min={1}
                      max={200}
                      value={weights.llm_rerank_top_k}
                      onInput={(e) =>
                        setWeights((w) =>
                          w
                            ? {
                                ...w,
                                llm_rerank_top_k:
                                  parseInt(
                                    (e.target as HTMLInputElement).value,
                                    10,
                                  ) || 30,
                              }
                            : w,
                        )
                      }
                    />
                  </Field>

                  <Field
                    label="LLM blend weight"
                    hint="0 = ignore LLM score entirely. 1 = replace classical score. 0.3 = recommended starting point."
                  >
                    <input
                      type="number"
                      class={INPUT}
                      min={0}
                      max={1}
                      step={0.05}
                      value={weights.llm_rerank_blend}
                      onInput={(e) =>
                        setWeights((w) =>
                          w
                            ? {
                                ...w,
                                llm_rerank_blend:
                                  parseFloat(
                                    (e.target as HTMLInputElement).value,
                                  ) || 0,
                              }
                            : w,
                        )
                      }
                    />
                  </Field>
                </div>
              )}
            </div>
          </Card>

          <div>
            <Button type="submit" loading={savingWeights}>
              Save ranking weights
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
