import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { LlmConfig } from '../../lib/types';
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

export function LlmConfigPage() {
  const [cfg, setCfg] = useState<LlmConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [pullModel, setPullModel] = useState('');
  const [pulling, setPulling] = useState(false);
  const [delModel, setDelModel] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  useEffect(() => {
    api
      .getLlmConfig()
      .then(setCfg)
      .catch((e: unknown) => {
        setFlash(e instanceof Error ? e.message : 'Failed to load config.');
      })
      .finally(() => setLoading(false));
  }, []);

  function showFlash(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(null), 4000);
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    if (!cfg) return;
    setSaving(true);
    try {
      await api.saveLlmConfig(cfg);
      showFlash('Settings saved.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setSaving(false);
    }
  }

  async function handlePull(e: Event) {
    e.preventDefault();
    if (!pullModel.trim()) return;
    setPulling(true);
    setActionMsg(null);
    try {
      const r = await api.pullOllamaModel(pullModel.trim());
      setActionMsg(r.message);
      setCfg((prev) =>
        prev && !prev.ollama_models.includes(pullModel.trim())
          ? { ...prev, ollama_models: [...prev.ollama_models, pullModel.trim()] }
          : prev,
      );
      setPullModel('');
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : 'Pull failed.');
    } finally {
      setPulling(false);
    }
  }

  async function handleDelete(e: Event) {
    e.preventDefault();
    if (!delModel) return;
    setDeleting(true);
    setActionMsg(null);
    try {
      const r = await api.deleteOllamaModel(delModel);
      setActionMsg(r.message);
      setCfg((prev) =>
        prev
          ? {
              ...prev,
              ollama_models: prev.ollama_models.filter((m) => m !== delModel),
            }
          : prev,
      );
      setDelModel('');
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setDeleting(false);
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
        {flash ?? 'Could not load LLM config.'}
      </p>
    );
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          LLM configuration
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Local Ollama on the host, or OpenRouter in the cloud.
        </p>
      </div>

      {flash && (
        <div class="px-4 py-3 text-sm rounded-lg bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
          {flash}
        </div>
      )}

      <Card>
        <CardHeader title="Provider settings" />
        <form onSubmit={handleSave} class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Provider">
            <select
              class={INPUT}
              value={cfg.provider}
              onChange={(e) =>
                setCfg((p) =>
                  p
                    ? { ...p, provider: (e.target as HTMLSelectElement).value }
                    : p,
                )
              }
            >
              <option value="ollama">Ollama (local, Metal GPU)</option>
              <option value="openrouter">OpenRouter</option>
              <option value="fallback">Fallback (local then cloud)</option>
            </select>
          </Field>

          <Field
            label="Model / Ollama tag"
            hint={`Ollama host: ${cfg.ollama_host}`}
          >
            <input
              class={INPUT}
              value={cfg.model}
              required
              onInput={(e) =>
                setCfg((p) =>
                  p
                    ? { ...p, model: (e.target as HTMLInputElement).value }
                    : p,
                )
              }
            />
          </Field>

          <Field label="OpenRouter model">
            <input
              class={INPUT}
              value={cfg.openrouter_model}
              placeholder="anthropic/claude-…"
              onInput={(e) =>
                setCfg((p) =>
                  p
                    ? {
                        ...p,
                        openrouter_model: (e.target as HTMLInputElement).value,
                      }
                    : p,
                )
              }
            />
          </Field>

          <div class="sm:col-span-2 space-y-1">
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                class="mt-0.5"
                checked={cfg.openrouter_pick_cheapest}
                onChange={(e) =>
                  setCfg((p) =>
                    p
                      ? {
                          ...p,
                          openrouter_pick_cheapest: (
                            e.target as HTMLInputElement
                          ).checked,
                        }
                      : p,
                  )
                }
              />
              <span class="text-sm text-slate-700 dark:text-slate-300">
                Prefer cheapest OpenRouter model (re-checked hourly)
              </span>
            </label>
            {cfg.openrouter_pick_cheapest && cfg.cheapest_model_id && (
              <p class="ml-6 text-xs text-slate-500 dark:text-slate-400">
                Currently using:{' '}
                <code class="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">
                  {cfg.cheapest_model_id}
                </code>
              </p>
            )}
          </div>

          <div class="sm:col-span-2">
            <Button type="submit" loading={saving}>
              Save settings
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <CardHeader
          title="Ollama models on host"
          description="Pull can take several minutes for large models."
        />

        {!cfg.ollama_reachable && (
          <div class="mb-4 px-4 py-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 text-sm text-amber-700 dark:text-amber-300">
            Ollama is not reachable at <code class="font-mono">{cfg.ollama_host}</code>.
            Model management is only available when Ollama is running locally.
          </div>
        )}

        {cfg.ollama_reachable && (
          <>
            {actionMsg && (
              <div class="mb-3 px-3 py-2 text-sm rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                {actionMsg}
              </div>
            )}

            <form onSubmit={handlePull} class="flex gap-2 mb-4">
              <input
                class={`${INPUT} flex-1`}
                placeholder="llama3.2:3b"
                value={pullModel}
                onInput={(e) => setPullModel((e.target as HTMLInputElement).value)}
                required
              />
              <Button type="submit" loading={pulling}>
                Pull
              </Button>
            </form>

            {cfg.ollama_models.length > 0 && (
              <form onSubmit={handleDelete} class="flex gap-2">
                <select
                  class={`${INPUT} flex-1`}
                  value={delModel}
                  onChange={(e) =>
                    setDelModel((e.target as HTMLSelectElement).value)
                  }
                  required
                >
                  <option value="">Select model to delete…</option>
                  {cfg.ollama_models.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <Button type="submit" variant="secondary" loading={deleting}>
                  Delete
                </Button>
              </form>
            )}

            {cfg.ollama_models.length === 0 && (
              <p class="text-sm text-slate-500 dark:text-slate-400">
                No models found. Run{' '}
                <code class="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">
                  ollama pull llama3.2:3b
                </code>{' '}
                on the host.
              </p>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
