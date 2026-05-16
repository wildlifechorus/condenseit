import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { ApiKey } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { Button } from '../../components/Button';
import { Spinner } from '../../components/Spinner';

const INPUT =
  'w-full px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

export function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingService, setDeletingService] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [service, setService] = useState('openrouter');
  const [keyValue, setKeyValue] = useState('');

  useEffect(() => {
    api
      .listKeys()
      .then(setKeys)
      .catch((e: unknown) => {
        setFlash(e instanceof Error ? e.message : 'Failed to load keys.');
      })
      .finally(() => setLoading(false));
  }, []);

  function showFlash(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(null), 4000);
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    if (!keyValue.trim()) return;
    setSaving(true);
    try {
      await api.saveKey(service, keyValue.trim());
      setKeyValue('');
      const updated = await api.listKeys();
      setKeys(updated);
      showFlash('Key saved.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(svc: string) {
    setDeletingService(svc);
    try {
      await api.deleteKey(svc);
      setKeys((prev) => prev.filter((k) => k.service !== svc));
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setDeletingService(null);
    }
  }

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
          API keys
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Encrypted at rest in SQLite. Used for OpenRouter and other services.
        </p>
      </div>

      {flash && (
        <div class="px-4 py-3 text-sm rounded-lg bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
          {flash}
        </div>
      )}

      <Card>
        <CardHeader title="Add or update key" />
        <form onSubmit={handleSave} class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label class="flex flex-col gap-1">
            <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Service
            </span>
            <select
              class={INPUT}
              value={service}
              onChange={(e) =>
                setService((e.target as HTMLSelectElement).value)
              }
            >
              <option value="openrouter">OpenRouter</option>
            </select>
          </label>
          <label class="flex flex-col gap-1">
            <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              API key
            </span>
            <input
              type="password"
              class={INPUT}
              required
              autoComplete="off"
              value={keyValue}
              onInput={(e) =>
                setKeyValue((e.target as HTMLInputElement).value)
              }
            />
          </label>
          <div>
            <Button type="submit" loading={saving}>
              Save key
            </Button>
          </div>
        </form>
      </Card>

      {keys.length > 0 && (
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="bg-slate-50 dark:bg-slate-800/60 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                <th class="text-left px-4 py-3">Service</th>
                <th class="text-left px-4 py-3">Preview</th>
                <th class="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr
                  key={k.service}
                  class="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30"
                >
                  <td class="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                    {k.service}
                  </td>
                  <td class="px-4 py-3 font-mono text-xs text-slate-500 dark:text-slate-400">
                    {k.key_preview}
                  </td>
                  <td class="px-4 py-3">
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={deletingService === k.service}
                      onClick={() => handleDelete(k.service)}
                    >
                      Delete
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
