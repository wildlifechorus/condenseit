import { useState, useEffect, useRef } from 'preact/hooks';
import { api } from '../../lib/api';
import type { DigestConfig, RankingWeights } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Button } from '../../components/Button';
import { Spinner } from '../../components/Spinner';

// ---------------------------------------------------------------------------
// Shared style tokens
// ---------------------------------------------------------------------------

const INPUT =
  'w-full px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200' +
  ' dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100' +
  ' focus:outline-none focus:ring-2 focus:ring-teal-500';

const TEXTAREA =
  INPUT + ' resize-none leading-relaxed';

// ---------------------------------------------------------------------------
// Preset bundles
// ---------------------------------------------------------------------------

/**
 * Each preset writes a full set of numeric weights to `RankingWeights`.
 * The `personalization_mode` label is persisted separately so the UI can
 * restore the selected tile on reload without comparing all weights.
 */
const PRESET_WEIGHTS: Record<
  'off' | 'balanced' | 'aggressive',
  Partial<RankingWeights>
> = {
  off: {
    tfidf_preference_weight: 0,
    category_preference_weight: 0,
    source_preference_weight: 0,
    implicit_signal_weight: 0,
    embedding_preference_weight: 0,
    topic_score_weight: 0,
    llm_rerank_enabled: false,
    llm_rerank_blend: 0,
    personalization_mode: 'off',
  },
  balanced: {
    tfidf_preference_weight: 0.35,
    category_preference_weight: 0.6,
    source_preference_weight: 0.3,
    implicit_signal_weight: 0.5,
    embedding_preference_weight: 0.5,
    topic_score_weight: 0.3,
    llm_rerank_blend: 0.4,
    personalization_mode: 'balanced',
  },
  aggressive: {
    tfidf_preference_weight: 0.6,
    category_preference_weight: 1.0,
    source_preference_weight: 0.5,
    implicit_signal_weight: 0.8,
    embedding_preference_weight: 1.0,
    topic_score_weight: 0.6,
    llm_rerank_enabled: true,
    llm_rerank_blend: 0.6,
    personalization_mode: 'aggressive',
  },
};

// ---------------------------------------------------------------------------
// Small shared field wrapper
// ---------------------------------------------------------------------------

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
    <label class='flex flex-col gap-1'>
      <span class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400'>
        {label}
      </span>
      {children}
      {hint && (
        <span class='text-xs text-slate-400 dark:text-slate-500'>{hint}</span>
      )}
    </label>
  );
}

// ---------------------------------------------------------------------------
// Tag-style input for language codes
// ---------------------------------------------------------------------------

function LanguageInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');

  function add(raw: string) {
    const code = raw.trim().toLowerCase().slice(0, 5);
    if (!code || value.includes(code)) { setDraft(''); return; }
    onChange([...value, code]);
    setDraft('');
    if (inputRef.current) inputRef.current.value = '';
  }

  function remove(code: string) { onChange(value.filter((l) => l !== code)); }

  function handleKeyDown(e: KeyboardEvent) {
    const t = e.target as HTMLInputElement;
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(t.value); }
    else if (e.key === 'Backspace' && !t.value && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div class='flex flex-wrap gap-1.5 p-2 min-h-[42px] bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg focus-within:ring-2 focus-within:ring-teal-500'>
      {value.map((code) => (
        <span
          key={code}
          class='inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-teal-100 dark:bg-teal-900/40 text-teal-800 dark:text-teal-200'
        >
          {code}
          <button
            type='button'
            onClick={() => remove(code)}
            class='hover:text-red-500 dark:hover:text-red-400 transition-colors leading-none'
            aria-label={`Remove ${code}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        type='text'
        class='flex-1 min-w-[80px] bg-transparent text-sm text-slate-900 dark:text-slate-100 focus:outline-none placeholder:text-slate-400'
        placeholder={value.length === 0 ? 'en, pt, de...' : ''}
        value={draft}
        onInput={(e) => setDraft((e.target as HTMLInputElement).value)}
        onKeyDown={handleKeyDown}
        onBlur={(e) => add((e.target as HTMLInputElement).value)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generic tag-style keyword input
// ---------------------------------------------------------------------------

function KeywordInput({
  value,
  onChange,
  placeholder,
  variant = 'neutral',
}: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
  variant?: 'neutral' | 'block' | 'demote';
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');

  function add(raw: string) {
    const phrase = raw.trim();
    if (!phrase || value.includes(phrase)) { setDraft(''); return; }
    onChange([...value, phrase]);
    setDraft('');
    if (inputRef.current) inputRef.current.value = '';
  }

  function remove(phrase: string) { onChange(value.filter((k) => k !== phrase)); }

  function handleKeyDown(e: KeyboardEvent) {
    const t = e.target as HTMLInputElement;
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(t.value); }
    else if (e.key === 'Backspace' && !t.value && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  const tagClass =
    variant === 'block'
      ? 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200'
      : variant === 'demote'
        ? 'bg-orange-100 dark:bg-orange-900/40 text-orange-800 dark:text-orange-200'
        : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300';

  return (
    <div class='flex flex-wrap gap-1.5 p-2 min-h-[42px] bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg focus-within:ring-2 focus-within:ring-teal-500'>
      {value.map((phrase) => (
        <span
          key={phrase}
          class={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${tagClass}`}
        >
          {phrase}
          <button
            type='button'
            onClick={() => remove(phrase)}
            class='hover:text-red-500 dark:hover:text-red-400 transition-colors leading-none'
            aria-label={`Remove ${phrase}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        type='text'
        class='flex-1 min-w-[120px] bg-transparent text-sm text-slate-900 dark:text-slate-100 focus:outline-none placeholder:text-slate-400'
        placeholder={value.length === 0 ? (placeholder ?? 'Type and press Enter...') : ''}
        value={draft}
        onInput={(e) => setDraft((e.target as HTMLInputElement).value)}
        onKeyDown={handleKeyDown}
        onBlur={(e) => add((e.target as HTMLInputElement).value)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Personalization preset tile
// ---------------------------------------------------------------------------

function PresetTile({
  title,
  description,
  active,
  onClick,
}: {
  title: string;
  description: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type='button'
      onClick={onClick}
      class={[
        'flex-1 text-left rounded-xl border-2 px-4 py-3 transition-all',
        active
          ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-900',
      ].join(' ')}
    >
      <p
        class={[
          'text-sm font-semibold',
          active
            ? 'text-teal-700 dark:text-teal-300'
            : 'text-slate-800 dark:text-slate-200',
        ].join(' ')}
      >
        {title}
        {active && (
          <span class='ml-2 text-xs font-medium px-1.5 py-0.5 rounded-full bg-teal-100 dark:bg-teal-800/50 text-teal-700 dark:text-teal-300'>
            active
          </span>
        )}
      </p>
      <p class='mt-1 text-xs text-slate-500 dark:text-slate-400 leading-snug'>
        {description}
      </p>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Collapsible section wrapper
// ---------------------------------------------------------------------------

function Collapsible({
  label,
  children,
}: {
  label: string;
  children: preact.ComponentChildren;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div class='border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden'>
      <button
        type='button'
        onClick={() => setOpen((v) => !v)}
        class='w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors'
      >
        {label}
        <svg
          class={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`}
          viewBox='0 0 20 20'
          fill='currentColor'
        >
          <path
            fill-rule='evenodd'
            d='M5.23 7.21a.75.75 0 011.06.02L10 11.17l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z'
            clip-rule='evenodd'
          />
        </svg>
      </button>
      {open && (
        <div class='px-4 pb-4 pt-2 space-y-5 border-t border-slate-200 dark:border-slate-700'>
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export function SettingsPage() {
  const [cfg, setCfg] = useState<DigestConfig | null>(null);
  const [loadingCfg, setLoadingCfg] = useState(true);
  const [savingCfg, setSavingCfg] = useState(false);

  const [weights, setWeights] = useState<RankingWeights | null>(null);
  const [savingW, setSavingW] = useState(false);

  const [flash, setFlash] = useState<{ text: string; ok: boolean } | null>(null);

  function showFlash(text: string, ok = true) {
    setFlash({ text, ok });
    setTimeout(() => setFlash(null), 4000);
  }

  useEffect(() => {
    api
      .getDigestConfig()
      .then(setCfg)
      .catch((e: unknown) => showFlash(e instanceof Error ? e.message : 'Failed to load settings.', false))
      .finally(() => setLoadingCfg(false));

    api
      .getRankingWeights()
      .then(setWeights)
      .catch(() => undefined);
  }, []);

  // ---- Digest config form -------------------------------------------------

  async function handleSaveCfg(e: Event) {
    e.preventDefault();
    if (!cfg) return;
    setSavingCfg(true);
    try {
      await api.saveDigestConfig(cfg);
      showFlash('Digest settings saved.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Save failed.', false);
    } finally {
      setSavingCfg(false);
    }
  }

  // ---- Ranking weights form ------------------------------------------------

  /** Apply a preset: merge preset weights into local state and mark mode. */
  function applyPreset(mode: 'off' | 'balanced' | 'aggressive') {
    setWeights((w) => (w ? { ...w, ...PRESET_WEIGHTS[mode] } : w));
  }

  /** When user edits any Advanced weight directly, flip to "custom". */
  function setWeightField<K extends keyof RankingWeights>(
    key: K,
    value: RankingWeights[K],
  ) {
    setWeights((w) =>
      w ? { ...w, [key]: value, personalization_mode: 'custom' } : w,
    );
  }

  async function handleSaveWeights(e: Event) {
    e.preventDefault();
    if (!weights) return;
    setSavingW(true);
    try {
      await api.saveRankingWeights(weights);
      showFlash('Personalization settings saved.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Failed to save.', false);
    } finally {
      setSavingW(false);
    }
  }

  // ---- Render -------------------------------------------------------------

  if (loadingCfg) {
    return (
      <div class='flex items-center justify-center py-20'>
        <Spinner size='lg' className='text-teal-600 dark:text-teal-400' />
      </div>
    );
  }

  if (!cfg) {
    return (
      <p class='text-sm text-red-600 dark:text-red-400 p-4'>
        {flash?.text ?? 'Could not load settings.'}
      </p>
    );
  }

  const mode = weights?.personalization_mode ?? 'balanced';

  return (
    <div class='space-y-8 pb-12'>

      {/* Page header */}
      <div>
        <h1 class='text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100'>
          Digest settings
        </h1>
        <p class='mt-1 text-sm text-slate-500 dark:text-slate-400'>
          Control what goes into your digest and how articles are ranked for you.
        </p>
      </div>

      {/* Flash banner */}
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

      {/* ================================================================
          SECTION 1 — What goes in your digest
          ================================================================ */}
      <form onSubmit={handleSaveCfg} class='space-y-5'>
        <div>
          <h2 class='text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100'>
            What goes in your digest
          </h2>
          <p class='mt-0.5 text-sm text-slate-500 dark:text-slate-400'>
            Article limits, how old articles can be, and which languages to include.
          </p>
        </div>

        <Card>
          <CardHeader title='Article limits' />
          <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
            <Field
              label='Max articles per digest'
              hint='How many articles appear in each digest. 20–30 is a good daily reading amount.'
            >
              <input
                type='number'
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
                          max_articles_per_digest:
                            parseInt((e.target as HTMLInputElement).value, 10) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <Field
              label='Article freshness (hours)'
              hint='Articles older than this are skipped. 36 = last day and a half. Set to 0 for no limit.'
            >
              <input
                type='number'
                class={INPUT}
                min={0}
                required
                value={cfg.max_article_age_hours}
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          max_article_age_hours:
                            parseInt((e.target as HTMLInputElement).value, 10) || 0,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <div class='sm:col-span-2'>
              <label class='flex items-start gap-2 cursor-pointer'>
                <input
                  type='checkbox'
                  class='mt-0.5'
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
                <span class='text-sm text-slate-700 dark:text-slate-300'>
                  <span class='font-medium'>Spread articles across categories</span>
                  <span class='block text-xs text-slate-500 dark:text-slate-400 mt-0.5'>
                    Reserves at least one slot per topic category before ranking
                    takes over. Keeps the digest varied instead of front-loading
                    one topic.
                  </span>
                </span>
              </label>
            </div>

            {cfg.balance_digest_categories && (
              <Field
                label='Max per category'
                hint='Cap on how many articles one category can take. Prevents a single busy topic from dominating.'
              >
                <input
                  type='number'
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
                            max_articles_per_category:
                              parseInt((e.target as HTMLInputElement).value, 10) || 1,
                          }
                        : p,
                    )
                  }
                />
              </Field>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader
            title='Language filter'
            description='Control which languages are collected and the language used in summaries.'
          />
          <div class='space-y-4'>
            <Field
              label='Collect articles in these languages'
              hint='ISO 639-1 codes (en, pt, de…). Type a code and press Enter. Leave empty to accept all languages.'
            >
              <LanguageInput
                value={cfg.preferred_languages}
                onChange={(langs) =>
                  setCfg((p) => (p ? { ...p, preferred_languages: langs } : p))
                }
              />
            </Field>

            <Field
              label='Write summaries in'
              hint="ISO 639-1 code for the digest output language (e.g. en, fr). Use 'source' to match each article's own language."
            >
              <input
                type='text'
                class={INPUT}
                value={cfg.digest_language ?? 'en'}
                placeholder='en'
                onInput={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          digest_language:
                            (e.target as HTMLInputElement).value
                              .trim()
                              .toLowerCase() || 'en',
                        }
                      : p,
                  )
                }
              />
            </Field>
          </div>
        </Card>

        {/* ================================================================
            SECTION 2 — Things to avoid
            ================================================================ */}
        <div class='pt-2'>
          <h2 class='text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100'>
            Things to avoid
          </h2>
          <p class='mt-0.5 text-sm text-slate-500 dark:text-slate-400'>
            Two ways to keep unwanted content out — choose the right one for your
            situation.
          </p>
        </div>

        <Card>
          <CardHeader
            title='Block completely'
            description='Articles whose title or description contains any of these phrases are removed before ranking — they will never appear, no matter how well they score.'
          />
          <Field
            label='Blocked phrases'
            hint='Good for promotional content, irrelevant sections, or junk your sources occasionally push. Example: "sponsored post", "press release".'
          >
            <KeywordInput
              value={cfg.exclude_keywords}
              variant='block'
              placeholder='sponsored post, press release...'
              onChange={(keywords) =>
                setCfg((p) => (p ? { ...p, exclude_keywords: keywords } : p))
              }
            />
          </Field>
        </Card>

        <Card>
          <CardHeader
            title='Show me less of this'
            description='Articles on these topics are penalised in ranking but not removed. They may still appear if nothing better is available. Topics you rate 1–2 stars are added here automatically by the learning engine.'
          />
          <Field
            label='Topics to demote'
            hint='Good for broad topics you sometimes tolerate but mostly skip. Use specific words that appear in article text — "world cup" works better than "sports". Multi-word phrases match only when all words appear.'
          >
            <KeywordInput
              value={cfg.disliked_keywords ?? []}
              variant='demote'
              placeholder='world cup, celebrity, box office...'
              onChange={(keywords) =>
                setCfg((p) => (p ? { ...p, disliked_keywords: keywords } : p))
              }
            />
          </Field>
        </Card>

        {/* ================================================================
            SECTION 3 — Summary style
            ================================================================ */}
        <div class='pt-2'>
          <h2 class='text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100'>
            Summary style
          </h2>
          <p class='mt-0.5 text-sm text-slate-500 dark:text-slate-400'>
            Control how much the AI writes per article.
          </p>
        </div>

        <Card>
          <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
            <Field
              label='Key takeaways per article'
              hint='Bullet points the AI produces per article (1–10).'
            >
              <input
                type='number'
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
                          max_key_takeaways:
                            parseInt((e.target as HTMLInputElement).value, 10) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>

            <Field
              label='Summary paragraphs per article'
              hint='Paragraphs of prose in each article summary (1–10).'
            >
              <input
                type='number'
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
                          max_summary_paragraphs:
                            parseInt((e.target as HTMLInputElement).value, 10) || 1,
                        }
                      : p,
                  )
                }
              />
            </Field>
          </div>
        </Card>

        {/* ================================================================
            SECTION 4 — YouTube transcription
            ================================================================ */}
        <Card>
          <CardHeader
            title='YouTube transcription'
            description='When enabled, videos without captions are transcribed via Whisper. Requires an OpenRouter API key and yt-dlp installed on the server.'
          />
          <div class='space-y-4'>
            <label class='flex items-start gap-2 cursor-pointer'>
              <input
                type='checkbox'
                class='mt-0.5'
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
              <span class='text-sm text-slate-700 dark:text-slate-300'>
                Enable audio transcription for YouTube videos (billed per second of audio)
              </span>
            </label>

            {cfg.youtube_transcription_enabled && (
              <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                <Field
                  label='Whisper model'
                  hint='turbo is fast and cheap; large-v3 is highest accuracy.'
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
                    <option value='openai/whisper-large-v3-turbo'>
                      whisper-large-v3-turbo (fast, cheap)
                    </option>
                    <option value='openai/whisper-large-v3'>
                      whisper-large-v3 (best quality)
                    </option>
                  </select>
                </Field>

                <Field
                  label='Max video duration (seconds)'
                  hint='Videos longer than this are skipped. Default 1800 (30 min).'
                >
                  <input
                    type='number'
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
          <Button type='submit' loading={savingCfg}>
            Save digest settings
          </Button>
        </div>
      </form>

      {/* ================================================================
          SECTION 5 — Personalization
          ================================================================ */}
      {weights && (
        <form onSubmit={handleSaveWeights} class='space-y-5'>
          <div>
            <h2 class='text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100'>
              Personalization
            </h2>
            <p class='mt-0.5 text-sm text-slate-500 dark:text-slate-400'>
              How strongly the engine uses your star ratings and reading habits to
              re-order articles. Changes take effect on the next digest run.
            </p>
          </div>

          {/* Preset tiles */}
          <Card>
            <CardHeader
              title='Learning intensity'
              description='Choose how aggressively your ratings shape the digest. You can fine-tune individual signals in Advanced below.'
            />
            <div class='flex flex-col sm:flex-row gap-3'>
              <PresetTile
                title='Off'
                description='No personalisation. Articles are ordered purely by recency and your keyword boosts.'
                active={mode === 'off'}
                onClick={() => applyPreset('off')}
              />
              <PresetTile
                title='Balanced'
                description='Recommended. Learns gradually from your ratings, reading, and saves without over-fitting on early signals.'
                active={mode === 'balanced'}
                onClick={() => applyPreset('balanced')}
              />
              <PresetTile
                title='Aggressive'
                description='Strong personalisation. Needs more ratings to work well but produces a tighter, more opinionated digest.'
                active={mode === 'aggressive'}
                onClick={() => applyPreset('aggressive')}
              />
              {mode === 'custom' && (
                <PresetTile
                  title='Custom'
                  description='Your own mix from the Advanced section below.'
                  active={true}
                  onClick={() => {}}
                />
              )}
            </div>
          </Card>

          {/* Reader profile */}
          <Card>
            <CardHeader
              title='Reader profile'
              description='Tell the AI who you are. This description is sent to the AI reranker so it can order stories with your interests in mind. The learning engine also fills this in automatically when you use "Seed with AI" on the Profile page.'
            />
            <Field
              label='About you'
              hint='Plain English. E.g. "Developer focused on self-hosting, open-source, and infosec. Not interested in mainstream news or celebrity content."'
            >
              <textarea
                rows={3}
                class={TEXTAREA}
                value={weights.profile_summary ?? ''}
                placeholder='Describe your interests in plain language...'
                onInput={(e) =>
                  setWeights((w) =>
                    w
                      ? {
                          ...w,
                          profile_summary: (e.target as HTMLTextAreaElement).value,
                        }
                      : w,
                  )
                }
              />
            </Field>
          </Card>

          {/* LLM reranker toggle (simple) */}
          <Card>
            <CardHeader
              title='AI re-ordering'
              description='After classical scoring, send your top candidates to an AI with your reader profile. The AI score is blended with the classical score. One extra AI call per digest run.'
            />
            <label class='flex items-start gap-2 cursor-pointer'>
              <input
                type='checkbox'
                class='mt-0.5'
                checked={weights.llm_rerank_enabled}
                onChange={(e) =>
                  setWeights((w) =>
                    w
                      ? {
                          ...w,
                          llm_rerank_enabled: (e.target as HTMLInputElement).checked,
                        }
                      : w,
                  )
                }
              />
              <span class='text-sm text-slate-700 dark:text-slate-300'>
                Let the AI re-order my top stories using my reader profile
              </span>
            </label>
          </Card>

          {/* Advanced collapsible */}
          <Collapsible label='Advanced — manual signal tuning'>
            <p class='text-xs text-slate-400 dark:text-slate-500'>
              Editing anything here switches your preset to "Custom". Each signal
              adds to the article's total ranking score.
            </p>

            {/* Explicit ratings */}
            <div>
              <p class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-3'>
                Signals from your star ratings
              </p>
              <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                <Field
                  label='Content similarity weight'
                  hint='How much word-level content similarity to your liked articles influences ranking (0 = off, 5 = very strong).'
                >
                  <input
                    type='number' class={INPUT} min={0} max={5} step={0.05}
                    value={weights.tfidf_preference_weight}
                    onInput={(e) =>
                      setWeightField(
                        'tfidf_preference_weight',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Category preference weight'
                  hint='Boost/demote articles based on how you rated their category on average (0 = off).'
                >
                  <input
                    type='number' class={INPUT} min={0} max={5} step={0.05}
                    value={weights.category_preference_weight}
                    onInput={(e) =>
                      setWeightField(
                        'category_preference_weight',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Source preference weight'
                  hint='Boost/demote articles based on how you rated their source feed on average (0 = off).'
                >
                  <input
                    type='number' class={INPUT} min={0} max={5} step={0.05}
                    value={weights.source_preference_weight}
                    onInput={(e) =>
                      setWeightField(
                        'source_preference_weight',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Min star ratings to activate learning'
                  hint='How many star ratings are needed before the engine starts personalising. Lower = learns faster, but early ratings have more influence.'
                >
                  <input
                    type='number' class={INPUT} min={1} max={1000}
                    value={weights.min_ratings_for_learning}
                    onInput={(e) =>
                      setWeightField(
                        'min_ratings_for_learning',
                        parseInt((e.target as HTMLInputElement).value, 10) || 1,
                      )
                    }
                  />
                </Field>
              </div>
            </div>

            {/* Implicit signals */}
            <div>
              <p class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-3'>
                Signals from reading behaviour
              </p>
              <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                <Field
                  label='Behaviour signal weight'
                  hint='How much reading, saving, and dismissing articles influences ranking relative to star ratings. 0 = disabled, 1 = same weight as star ratings.'
                >
                  <input
                    type='number' class={INPUT} min={0} max={1} step={0.05}
                    value={weights.implicit_signal_weight}
                    onInput={(e) =>
                      setWeightField(
                        'implicit_signal_weight',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Rating decay half-life (days)'
                  hint='Older ratings count less. After this many days, a rating is worth half as much. 30 days is recommended.'
                >
                  <input
                    type='number' class={INPUT} min={1} max={3650}
                    value={weights.rating_decay_half_life_days}
                    onInput={(e) =>
                      setWeightField(
                        'rating_decay_half_life_days',
                        parseInt((e.target as HTMLInputElement).value, 10) || 30,
                      )
                    }
                  />
                </Field>
              </div>
            </div>

            {/* Semantic embeddings */}
            <div>
              <p class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-3'>
                Semantic similarity (requires embedding provider)
              </p>
              <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                <Field
                  label='Embedding provider'
                  hint='off = disabled. ollama = free local. openrouter = cloud (~$0.001/run).'
                >
                  <select
                    class={INPUT}
                    value={weights.embedding_provider}
                    onChange={(e) => {
                      const provider = (e.target as HTMLSelectElement).value as
                        | 'off'
                        | 'ollama'
                        | 'openrouter'
                        | 'openai';
                      const defaultModel =
                        provider === 'ollama'
                          ? 'nomic-embed-text'
                          : provider === 'openrouter'
                            ? 'openai/text-embedding-3-small'
                            : provider === 'openai'
                              ? 'text-embedding-3-small'
                              : '';
                      setWeights((w) =>
                        w
                          ? {
                              ...w,
                              embedding_provider: provider,
                              embedding_model:
                                w.embedding_model &&
                                !['nomic-embed-text', 'openai/text-embedding-3-small', 'text-embedding-3-small'].includes(w.embedding_model)
                                  ? w.embedding_model
                                  : defaultModel,
                              personalization_mode: 'custom',
                            }
                          : w,
                      );
                    }}
                  >
                    <option value='off'>off</option>
                    <option value='ollama'>ollama (free, local)</option>
                    <option value='openrouter'>openrouter (cloud)</option>
                    <option value='openai'>openai-compatible (custom endpoint)</option>
                  </select>
                </Field>

                {weights.embedding_provider !== 'off' && (
                  <Field
                    label='Embedding model'
                    hint={
                      weights.embedding_provider === 'openrouter'
                        ? 'openai/text-embedding-3-small is cheapest.'
                        : 'nomic-embed-text works well for news.'
                    }
                  >
                    <input
                      type='text' class={INPUT}
                      value={weights.embedding_model}
                      placeholder={
                        weights.embedding_provider === 'openrouter'
                          ? 'openai/text-embedding-3-small'
                          : 'nomic-embed-text'
                      }
                      onInput={(e) =>
                        setWeightField(
                          'embedding_model',
                          (e.target as HTMLInputElement).value,
                        )
                      }
                    />
                  </Field>
                )}

                {weights.embedding_provider !== 'off' && (
                  <Field
                    label='Embedding similarity weight'
                    hint='How strongly semantic closeness to your liked articles influences ranking (0 = off, 5 = very strong).'
                  >
                    <input
                      type='number' class={INPUT} min={0} max={5} step={0.05}
                      value={weights.embedding_preference_weight}
                      onInput={(e) =>
                        setWeightField(
                          'embedding_preference_weight',
                          parseFloat((e.target as HTMLInputElement).value) || 0,
                        )
                      }
                    />
                  </Field>
                )}

                {weights.embedding_provider !== 'off' && (
                  <div class='sm:col-span-2 space-y-3'>
                    <label class='flex items-start gap-2 cursor-pointer'>
                      <input
                        type='checkbox' class='mt-0.5'
                        checked={weights.semantic_dedup_enabled}
                        onChange={(e) =>
                          setWeightField(
                            'semantic_dedup_enabled',
                            (e.target as HTMLInputElement).checked,
                          )
                        }
                      />
                      <span class='text-sm text-slate-700 dark:text-slate-300'>
                        Remove duplicate stories covering the same event
                      </span>
                    </label>
                    {weights.semantic_dedup_enabled && (
                      <div class='pl-6'>
                        <Field
                          label='Duplicate similarity threshold (0.5–1.0)'
                          hint='How similar two articles must be to count as the same story. 0.85 is recommended.'
                        >
                          <input
                            type='number' class={INPUT} min={0.5} max={1.0} step={0.01}
                            value={weights.semantic_dedup_threshold}
                            onInput={(e) =>
                              setWeightField(
                                'semantic_dedup_threshold',
                                parseFloat((e.target as HTMLInputElement).value) || 0.85,
                              )
                            }
                          />
                        </Field>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Topic enrichment */}
            <div>
              <p class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-3'>
                AI topic enrichment
              </p>
              <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                <Field
                  label='Topic overlap weight'
                  hint='Influence of AI-extracted topic similarity to your rated articles (0 = off). Requires at least one summarised and rated article.'
                >
                  <input
                    type='number' class={INPUT} min={0} max={5} step={0.05}
                    value={weights.topic_score_weight}
                    onInput={(e) =>
                      setWeightField(
                        'topic_score_weight',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>
              </div>
            </div>

            {/* LLM reranker advanced */}
            {weights.llm_rerank_enabled && (
              <div>
                <p class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-3'>
                  AI re-ordering settings
                </p>
                <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                  <Field
                    label='Reranker model'
                    hint='Leave blank to use the same model as the summariser. Cheap models (e.g. deepseek/deepseek-v3) work well here.'
                  >
                    <input
                      type='text' class={INPUT}
                      value={weights.llm_rerank_model}
                      placeholder='(same as summariser)'
                      onInput={(e) =>
                        setWeightField(
                          'llm_rerank_model',
                          (e.target as HTMLInputElement).value,
                        )
                      }
                    />
                  </Field>

                  <Field
                    label='Candidates sent to AI (top-K)'
                    hint='Number of top articles the AI sees for re-ordering (1–200).'
                  >
                    <input
                      type='number' class={INPUT} min={1} max={200}
                      value={weights.llm_rerank_top_k}
                      onInput={(e) =>
                        setWeightField(
                          'llm_rerank_top_k',
                          parseInt((e.target as HTMLInputElement).value, 10) || 30,
                        )
                      }
                    />
                  </Field>

                  <Field
                    label='AI blend weight (0–1)'
                    hint='0 = ignore AI score. 1 = use AI score only. 0.4 = recommended starting point.'
                  >
                    <input
                      type='number' class={INPUT} min={0} max={1} step={0.05}
                      value={weights.llm_rerank_blend}
                      onInput={(e) =>
                        setWeightField(
                          'llm_rerank_blend',
                          parseFloat((e.target as HTMLInputElement).value) || 0,
                        )
                      }
                    />
                  </Field>
                </div>
              </div>
            )}

            {/* Category gate */}
            <div>
              <p class='text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 mb-3'>
                Category gate
              </p>
              <p class='text-xs text-slate-400 dark:text-slate-500 mb-3'>
                Optionally exclude or limit categories you consistently rate poorly.
                Default −5.0 means the gate is off. Raise toward 0 to activate (e.g.
                −1.5 to exclude, −0.5 to demote).
              </p>
              <div class='grid grid-cols-1 sm:grid-cols-2 gap-4'>
                <Field
                  label='Exclude threshold (−5 to 0)'
                  hint='Categories with learned score at/below this are dropped entirely.'
                >
                  <input
                    type='number' class={INPUT} min={-5} max={0} step={0.1}
                    value={weights.category_exclude_threshold}
                    onInput={(e) =>
                      setWeightField(
                        'category_exclude_threshold',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Demote threshold (−5 to 0)'
                  hint='Categories at/below this lose their guaranteed slot and are capped.'
                >
                  <input
                    type='number' class={INPUT} min={-5} max={0} step={0.1}
                    value={weights.category_demote_threshold}
                    onInput={(e) =>
                      setWeightField(
                        'category_demote_threshold',
                        parseFloat((e.target as HTMLInputElement).value) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Demoted category cap'
                  hint='Max articles allowed from a demoted category per digest.'
                >
                  <input
                    type='number' class={INPUT} min={0} max={50}
                    value={weights.category_demote_cap}
                    onInput={(e) =>
                      setWeightField(
                        'category_demote_cap',
                        parseInt((e.target as HTMLInputElement).value, 10) || 0,
                      )
                    }
                  />
                </Field>

                <Field
                  label='Min ratings before gating'
                  hint='A category must have at least this many ratings before it can be gated. Protects categories you have not rated much yet.'
                >
                  <input
                    type='number' class={INPUT} min={1} max={1000}
                    value={weights.category_min_ratings}
                    onInput={(e) =>
                      setWeightField(
                        'category_min_ratings',
                        parseInt((e.target as HTMLInputElement).value, 10) || 1,
                      )
                    }
                  />
                </Field>
              </div>
            </div>
          </Collapsible>

          <div>
            <Button type='submit' loading={savingW}>
              Save personalization settings
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
