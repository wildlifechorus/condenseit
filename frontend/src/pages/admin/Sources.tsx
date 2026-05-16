import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { Source } from '../../lib/types';
import { Badge, kindVariant } from '../../components/Badge';
import { Button } from '../../components/Button';
import { Card, CardHeader } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Spinner } from '../../components/Spinner';

export function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [addLoading, setAddLoading] = useState(false);
  const [opmlLoading, setOpmlLoading] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    api
      .listSources()
      .then(setSources)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load sources.');
      })
      .finally(() => setLoading(false));
  }

  function showFlash(msg: string) {
    setFlash(msg);
    setTimeout(() => setFlash(null), 4000);
  }

  async function handleAdd(e: Event) {
    e.preventDefault();
    const form = e.target as HTMLFormElement;
    const data = new FormData(form);
    setAddLoading(true);
    try {
      await api.addSource(data);
      form.reset();
      load();
      showFlash('Source added.');
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Failed to add source.');
    } finally {
      setAddLoading(false);
    }
  }

  async function handleDelete(id: number) {
    setDeletingId(id);
    try {
      await api.deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'Failed to delete source.');
    } finally {
      setDeletingId(null);
    }
  }

  async function handleImportOpml(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.[0]) return;
    const data = new FormData();
    data.append('file', input.files[0]);
    setOpmlLoading(true);
    try {
      const res = await api.importOpml(data);
      input.value = '';
      load();
      showFlash(`Imported ${res.added} source${res.added !== 1 ? 's' : ''}.`);
    } catch (err) {
      showFlash(err instanceof Error ? err.message : 'OPML import failed.');
    } finally {
      setOpmlLoading(false);
    }
  }

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  if (error) {
    return <p class="text-sm text-red-600 dark:text-red-400 p-4">{error}</p>;
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Sources
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          RSS feeds, YouTube channels, and website change monitors.
        </p>
      </div>

      {flash && (
        <div class="px-4 py-3 text-sm rounded-lg bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
          {flash}
        </div>
      )}

      {/* Add source form */}
      <Card>
        <CardHeader title="Add source" />
        <form onSubmit={handleAdd} class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Type">
            <select name="source_type" class={inputCls}>
              <option value="rss">RSS</option>
              <option value="youtube">YouTube</option>
              <option value="website">Website watch</option>
            </select>
          </Field>
          <Field label="Name">
            <input name="name" required class={inputCls} />
          </Field>
          <Field label="URL" className="sm:col-span-2">
            <input
              name="url"
              required
              placeholder="https://…"
              class={inputCls}
            />
          </Field>
          <Field label="Category">
            <input name="category" defaultValue="General" class={inputCls} />
          </Field>
          <Field label="Priority">
            <input
              name="priority"
              type="number"
              defaultValue="2"
              min="1"
              max="5"
              class={inputCls}
            />
          </Field>
          <Field label="YouTube channel ID" className="sm:col-span-2">
            <input name="channel_id" placeholder="UC…" class={inputCls} />
          </Field>
          <div class="sm:col-span-2">
            <Button type="submit" loading={addLoading}>
              Add source
            </Button>
          </div>
        </form>
      </Card>

      {/* OPML import/export */}
      <Card>
        <CardHeader title="OPML" />
        <div class="flex flex-wrap items-center gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <span class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer">
              {opmlLoading ? 'Importing…' : 'Import OPML'}
            </span>
            <input
              type="file"
              accept=".opml,.xml,text/xml"
              class="sr-only"
              onChange={handleImportOpml}
              disabled={opmlLoading}
            />
          </label>
          <a
            href={api.exportOpmlUrl()}
            download="condenseit-sources.opml"
            class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            Export OPML
          </a>
        </div>
      </Card>

      {/* Sources table */}
      {sources.length === 0 ? (
        <EmptyState title="No sources yet" description="Add your first RSS feed, YouTube channel, or website above." />
      ) : (
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-sm border-collapse">
              <thead>
                <tr class="bg-slate-50 dark:bg-slate-800/60 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <th class="text-left px-4 py-3">Type</th>
                  <th class="text-left px-4 py-3">Name</th>
                  <th class="text-left px-4 py-3 hidden md:table-cell">URL</th>
                  <th class="text-left px-4 py-3">Category</th>
                  <th class="text-left px-4 py-3 hidden lg:table-cell">Health</th>
                  <th class="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr
                    key={s.id}
                    class="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30"
                  >
                    <td class="px-4 py-3">
                      <Badge variant={kindVariant(s.type)}>{s.type}</Badge>
                    </td>
                    <td class="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                      {s.name}
                    </td>
                    <td class="px-4 py-3 hidden md:table-cell max-w-xs truncate text-slate-500 dark:text-slate-400 font-mono text-xs">
                      {s.url}
                    </td>
                    <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                      {s.category}
                    </td>
                    <td class="px-4 py-3 hidden lg:table-cell text-xs text-slate-500">
                      {s.last_status ? (
                        <div class="flex flex-col gap-0.5">
                          <Badge variant={kindVariant(s.last_status === 'ok' ? 'ok' : 'error')}>
                            {s.last_status}
                          </Badge>
                          {s.last_item_count != null && (
                            <span>{s.last_item_count} items</span>
                          )}
                          {s.last_checked_at && (
                            <span title={s.last_error ?? ''}>
                              {s.last_checked_at.slice(0, 16)}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span class="text-slate-400">—</span>
                      )}
                    </td>
                    <td class="px-4 py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        loading={deletingId === s.id}
                        onClick={() => handleDelete(s.id)}
                      >
                        Delete
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const inputCls =
  'w-full px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

function Field({
  label,
  children,
  className = '',
}: {
  label: string;
  children: preact.ComponentChildren;
  className?: string;
}) {
  return (
    <label class={`flex flex-col gap-1 ${className}`}>
      <span class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </span>
      {children}
    </label>
  );
}
