import { useState, useEffect, useRef } from 'preact/hooks';
import { api } from '../../lib/api';
import type { DigestConfig } from '../../lib/types';
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

export function SettingsPage() {
  const [cfg, setCfg] = useState<DigestConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<{ text: string; ok: boolean } | null>(
    null,
  );

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

        <div>
          <Button type="submit" loading={saving}>
            Save settings
          </Button>
        </div>
      </form>
    </div>
  );
}
