import { useState, useEffect, useMemo } from 'preact/hooks';
import { api } from '../../lib/api';
import type { Source } from '../../lib/types';
import { Badge, kindVariant } from '../../components/Badge';
import { Button } from '../../components/Button';
import { Card, CardHeader } from '../../components/Card';
import { EmptyState } from '../../components/EmptyState';
import { Spinner } from '../../components/Spinner';

/** Shared Tailwind class string for text inputs and selects. */
const inputCls =
  'w-full px-3 py-2 text-sm bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500';

const PRIORITY_LABELS: Record<number, string> = {
  1: 'High',
  2: 'Normal',
  3: 'Low',
  4: 'Lower',
  5: 'Lowest',
};

const PRIORITY_COLORS: Record<number, string> = {
  1: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  2: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
  3: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  4: 'bg-blue-50 text-blue-500 dark:bg-blue-900/20 dark:text-blue-500',
  5: 'bg-slate-50 text-slate-400 dark:bg-slate-800/50 dark:text-slate-500',
};

export function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(
    null,
  );
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [addLoading, setAddLoading] = useState(false);
  const [opmlLoading, setOpmlLoading] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const [addFormOpen, setAddFormOpen] = useState(false);
  const [sourceType, setSourceType] = useState('rss');
  const [gnewsQuery, setGnewsQuery] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(
    null,
  );

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    api
      .listSources()
      .then(setSources)
      .catch((e: unknown) => {
        setError(
          e instanceof Error ? e.message : 'Failed to load sources.',
        );
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
      setSourceType('rss');
      setGnewsQuery('');
      setAddFormOpen(false);
      load();
      showFlash('Source added.');
    } catch (err) {
      showFlash(
        err instanceof Error ? err.message : 'Failed to add source.',
      );
    } finally {
      setAddLoading(false);
    }
  }

  async function handleDelete(id: number) {
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id);
      setTimeout(() => setConfirmDeleteId(null), 3000);
      return;
    }
    setDeletingId(id);
    setConfirmDeleteId(null);
    try {
      await api.deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      showFlash(
        err instanceof Error
          ? err.message
          : 'Failed to delete source.',
      );
    } finally {
      setDeletingId(null);
    }
  }

  async function handleToggle(id: number, currentEnabled: number) {
    const next = currentEnabled === 0;
    // Optimistically update UI before the request completes.
    setSources((prev) =>
      prev.map((s) =>
        s.id === id ? { ...s, enabled: next ? 1 : 0 } : s,
      ),
    );
    setTogglingId(id);
    try {
      await api.toggleSource(id, next);
    } catch (err) {
      // Revert on failure.
      setSources((prev) =>
        prev.map((s) =>
          s.id === id ? { ...s, enabled: currentEnabled } : s,
        ),
      );
      showFlash(
        err instanceof Error
          ? err.message
          : 'Failed to toggle source.',
      );
    } finally {
      setTogglingId(null);
    }
  }

  async function handleImportOpml(e: Event) {
    const input = e.target as HTMLInputElement;
    if (!input.files?.[0]) {
      return;
    }
    const data = new FormData();
    data.append('file', input.files[0]);
    setOpmlLoading(true);
    try {
      const res = await api.importOpml(data);
      input.value = '';
      load();
      showFlash(
        `Imported ${res.added} source${res.added !== 1 ? 's' : ''}.`,
      );
    } catch (err) {
      showFlash(
        err instanceof Error ? err.message : 'OPML import failed.',
      );
    } finally {
      setOpmlLoading(false);
    }
  }

  /** Unique categories derived from current sources. */
  const categories = useMemo(() => {
    const cats = new Set(sources.map((s) => s.category));
    return Array.from(cats).sort();
  }, [sources]);

  /** Sources filtered by search query and active category. */
  const filteredSources = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return sources.filter((s) => {
      if (
        activeCategory &&
        s.category !== activeCategory
      ) {
        return false;
      }
      if (!q) {
        return true;
      }
      return (
        s.name.toLowerCase().includes(q) ||
        s.url.toLowerCase().includes(q) ||
        s.category.toLowerCase().includes(q)
      );
    });
  }, [sources, searchQuery, activeCategory]);

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner
          size="lg"
          className="text-teal-600 dark:text-teal-400"
        />
      </div>
    );
  }

  if (error) {
    return (
      <p class="text-sm text-red-600 dark:text-red-400 p-4">
        {error}
      </p>
    );
  }

  return (
    <div class="space-y-5">
      {/* Page header */}
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Sources
          </h1>
          {sources.length > 0 && (
            <span class="inline-flex items-center px-2.5 py-0.5 text-xs font-semibold rounded-full bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300">
              {sources.length}
            </span>
          )}
        </div>
        <div class="flex items-center gap-2">
          <Button
            size="sm"
            onClick={() => setAddFormOpen((o) => !o)}
          >
            {addFormOpen ? 'Cancel' : 'Add source'}
          </Button>
        </div>
      </div>
      <p class="text-sm text-slate-500 dark:text-slate-400 -mt-3">
        RSS, YouTube, website monitors, Google News searches, Hacker News, Reddit, and GitHub Releases.
      </p>

      {flash && (
        <div class="px-4 py-3 text-sm rounded-lg bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
          {flash}
        </div>
      )}

      {/* Collapsible add-source form */}
      {addFormOpen && (
        <Card>
          <CardHeader title="Add source" />
          <form
            onSubmit={handleAdd}
            class="grid grid-cols-1 sm:grid-cols-2 gap-3"
          >
            {/* --- Type selector --- */}
            <Field label="Type">
              <select
                name="source_type"
                class={inputCls}
                value={sourceType}
                onChange={(e) =>
                  setSourceType(
                    (e.target as HTMLSelectElement).value,
                  )
                }
              >
                <option value="rss">RSS</option>
                <option value="youtube">YouTube</option>
                <option value="website">Website watch</option>
                <option value="google_news">Google News search</option>
                <option value="hackernews">Hacker News</option>
                <option value="reddit">Reddit</option>
                <option value="github_releases">GitHub Releases</option>
              </select>
            </Field>

            {/* --- Name (always shown) --- */}
            <Field label="Name">
              <input name="name" required class={inputCls} />
            </Field>

            {/* --- URL (RSS / YouTube / Website only) --- */}
            {(sourceType === 'rss' ||
              sourceType === 'youtube' ||
              sourceType === 'website') && (
              <Field label="URL" className="sm:col-span-2">
                <input
                  name="url"
                  required
                  placeholder={
                    sourceType === 'youtube'
                      ? 'https://www.youtube.com/@channel'
                      : sourceType === 'website'
                        ? 'https://example.com/page-to-watch'
                        : 'https://example.com/feed.xml'
                  }
                  class={inputCls}
                />
                <span class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                  {sourceType === 'youtube'
                    ? 'Channel page URL or RSS feed URL'
                    : sourceType === 'website'
                      ? 'Page URL to monitor for changes'
                      : 'Direct RSS/Atom feed URL'}
                </span>
              </Field>
            )}

            {/* --- YouTube channel ID --- */}
            {sourceType === 'youtube' && (
              <Field
                label="YouTube channel ID"
                className="sm:col-span-2"
              >
                <input
                  name="channel_id"
                  placeholder="UC..."
                  class={inputCls}
                />
                <span class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                  Found in the channel's About page or URL
                </span>
              </Field>
            )}

            {/* --- Google News search query --- */}
            {sourceType === 'google_news' && (
              <>
                <Field label="Search query" className="sm:col-span-2">
                  <input
                    name="query"
                    required
                    placeholder='site:reuters.com when:1d  /  "AI" intitle:release'
                    value={gnewsQuery}
                    onInput={(e) =>
                      setGnewsQuery(
                        (e.target as HTMLInputElement).value,
                      )
                    }
                    class={inputCls}
                  />
                  <span class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                    Supports{' '}
                    <code class="font-mono">site:</code>,{' '}
                    <code class="font-mono">when:</code>,{' '}
                    <code class="font-mono">intitle:</code>,{' '}
                    <code class="font-mono">source:</code> operators
                  </span>
                </Field>
                {gnewsQuery && (
                  <p class="sm:col-span-2 text-xs font-mono text-slate-400 dark:text-slate-500 break-all">
                    {`https://news.google.com/rss/search?q=${encodeURIComponent(gnewsQuery)}&hl=en-US&gl=US&ceid=US:en`}
                  </p>
                )}
                <Field label="Language">
                  <input
                    name="language"
                    defaultValue="en"
                    placeholder="en"
                    class={inputCls}
                  />
                </Field>
                <Field label="Country">
                  <input
                    name="country"
                    defaultValue="US"
                    placeholder="US"
                    class={inputCls}
                  />
                </Field>
              </>
            )}

            {/* --- Hacker News --- */}
            {sourceType === 'hackernews' && (
              <>
                <Field label="Feed">
                  <select name="hn_feed" class={inputCls} defaultValue="top">
                    <option value="top">Top stories</option>
                    <option value="best">Best stories</option>
                    <option value="new">New stories</option>
                    <option value="ask">Ask HN</option>
                    <option value="show">Show HN</option>
                  </select>
                </Field>
                <Field label="Min score">
                  <input
                    name="hn_min_score"
                    type="number"
                    defaultValue="50"
                    min="0"
                    class={inputCls}
                  />
                  <span class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                    Skip stories below this score
                  </span>
                </Field>
                <Field label="Max items">
                  <input
                    name="hn_max_items"
                    type="number"
                    defaultValue="20"
                    min="1"
                    max="100"
                    class={inputCls}
                  />
                </Field>
              </>
            )}

            {/* --- Reddit --- */}
            {sourceType === 'reddit' && (
              <>
                <Field label="Subreddit" className="sm:col-span-2">
                  <input
                    name="subreddit"
                    required
                    placeholder="netsec"
                    class={inputCls}
                  />
                  <span class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                    Name only, without{' '}
                    <code class="font-mono">r/</code>
                  </span>
                </Field>
                <Field label="Sort">
                  <select name="reddit_sort" class={inputCls} defaultValue="hot">
                    <option value="hot">Hot</option>
                    <option value="new">New</option>
                    <option value="top">Top</option>
                    <option value="rising">Rising</option>
                  </select>
                </Field>
                <Field label="Time filter (for Top)">
                  <select
                    name="reddit_time_filter"
                    class={inputCls}
                    defaultValue="day"
                  >
                    <option value="hour">Past hour</option>
                    <option value="day">Past 24 h</option>
                    <option value="week">Past week</option>
                    <option value="month">Past month</option>
                    <option value="year">Past year</option>
                    <option value="all">All time</option>
                  </select>
                </Field>
                <Field label="Min score">
                  <input
                    name="reddit_min_score"
                    type="number"
                    defaultValue="10"
                    min="0"
                    class={inputCls}
                  />
                </Field>
                <Field label="Max items">
                  <input
                    name="reddit_max_items"
                    type="number"
                    defaultValue="20"
                    min="1"
                    max="100"
                    class={inputCls}
                  />
                </Field>
              </>
            )}

            {/* --- GitHub Releases --- */}
            {sourceType === 'github_releases' && (
              <Field label="Repository" className="sm:col-span-2">
                <input
                  name="github_repo"
                  required
                  placeholder="astral-sh/uv"
                  class={inputCls}
                />
                <span class="text-xs text-slate-400 dark:text-slate-500 mt-0.5">
                  Format: <code class="font-mono">owner/repo</code>
                </span>
              </Field>
            )}

            {/* --- Category & priority (always shown) --- */}
            <Field label="Category">
              <input
                name="category"
                defaultValue="General"
                class={inputCls}
              />
            </Field>
            <Field label="Priority">
              <select
                name="priority"
                class={inputCls}
                defaultValue="2"
              >
                <option value="1">1 - High</option>
                <option value="2">2 - Normal</option>
                <option value="3">3 - Low</option>
                <option value="4">4 - Lower</option>
                <option value="5">5 - Lowest</option>
              </select>
            </Field>

            <div class="sm:col-span-2">
              <Button type="submit" loading={addLoading}>
                Add source
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* OPML import/export */}
      <Card>
        <CardHeader title="OPML" />
        <div class="flex flex-wrap items-center gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <span class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors cursor-pointer">
              {opmlLoading ? 'Importing...' : 'Import OPML'}
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

      {/* Search + category filter */}
      {sources.length > 0 && (
        <div class="space-y-3">
          <div class="relative">
            <svg
              class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
              />
            </svg>
            <input
              type="text"
              placeholder="Search by name, URL, or category..."
              value={searchQuery}
              onInput={(e) =>
                setSearchQuery(
                  (e.target as HTMLInputElement).value,
                )
              }
              class={`${inputCls} pl-10`}
            />
          </div>

          {categories.length > 1 && (
            <div class="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setActiveCategory(null)}
                class={[
                  'px-2.5 py-1 text-xs font-medium rounded-full transition-colors',
                  activeCategory === null
                    ? 'bg-teal-600 text-white'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700',
                ].join(' ')}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() =>
                    setActiveCategory(
                      activeCategory === cat ? null : cat,
                    )
                  }
                  class={[
                    'px-2.5 py-1 text-xs font-medium rounded-full transition-colors',
                    activeCategory === cat
                      ? 'bg-teal-600 text-white'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700',
                  ].join(' ')}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Sources list */}
      {sources.length === 0 ? (
        <EmptyState
          title="No sources yet"
          description="Add your first source - RSS, YouTube, Google News search, Hacker News, Reddit, or GitHub Releases."
          action={
            <Button onClick={() => setAddFormOpen(true)}>
              Add source
            </Button>
          }
        />
      ) : filteredSources.length === 0 ? (
        <div class="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
          No sources match your search.
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div class="hidden md:block bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full text-sm border-collapse">
                <thead>
                  <tr class="bg-slate-50 dark:bg-slate-800/60 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                    <th class="text-left px-4 py-3">Type</th>
                    <th class="text-left px-4 py-3">Name</th>
                    <th class="text-left px-4 py-3">URL</th>
                    <th class="text-left px-4 py-3">Category</th>
                    <th class="text-left px-4 py-3">Priority</th>
                    <th class="text-left px-4 py-3">Health</th>
                    <th class="text-left px-4 py-3">Enabled</th>
                    <th class="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {filteredSources.map((s) => (
                    <tr
                      key={s.id}
                      class={[
                        'border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30',
                        s.enabled === 0
                          ? 'opacity-50'
                          : '',
                      ].join(' ')}
                    >
                      <td class="px-4 py-3">
                        <Badge variant={kindVariant(s.type)}>
                          {s.type}
                        </Badge>
                      </td>
                      <td class="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">
                        {s.name}
                      </td>
                      <td class="px-4 py-3 max-w-xs truncate text-slate-500 dark:text-slate-400 font-mono text-xs">
                        {s.url}
                      </td>
                      <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                        {s.category}
                      </td>
                      <td class="px-4 py-3">
                        <span
                          class={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${PRIORITY_COLORS[s.priority] ?? PRIORITY_COLORS[2]}`}
                        >
                          {PRIORITY_LABELS[s.priority] ??
                            `P${s.priority}`}
                        </span>
                      </td>
                      <td class="px-4 py-3 text-xs text-slate-500">
                        {s.last_status ? (
                          <div class="flex flex-col gap-0.5">
                            <Badge
                              variant={kindVariant(
                                s.last_status === 'ok'
                                  ? 'ok'
                                  : 'error',
                              )}
                            >
                              {s.last_status}
                            </Badge>
                            {s.last_item_count != null && (
                              <span>
                                {s.last_item_count} items
                              </span>
                            )}
                            {s.last_checked_at && (
                              <span title={s.last_error ?? ''}>
                                {s.last_checked_at.slice(0, 16)}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span class="text-slate-400">
                            &mdash;
                          </span>
                        )}
                      </td>
                      <td class="px-4 py-3">
                        <ToggleSwitch
                          enabled={s.enabled !== 0}
                          disabled={togglingId === s.id}
                          onChange={() =>
                            handleToggle(s.id, s.enabled ?? 1)
                          }
                        />
                      </td>
                      <td class="px-4 py-3">
                        <Button
                          variant={
                            confirmDeleteId === s.id
                              ? 'danger'
                              : 'ghost'
                          }
                          size="sm"
                          loading={deletingId === s.id}
                          onClick={() => handleDelete(s.id)}
                        >
                          {confirmDeleteId === s.id
                            ? 'Confirm'
                            : 'Delete'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div class="md:hidden space-y-3">
            {filteredSources.map((s) => (
              <div
                key={s.id}
                class={[
                  'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm p-4 space-y-2',
                  s.enabled === 0 ? 'opacity-50' : '',
                ].join(' ')}
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <p class="font-medium text-sm text-slate-900 dark:text-slate-100 truncate">
                      {s.name}
                    </p>
                    <p class="text-xs text-slate-500 dark:text-slate-400 font-mono truncate mt-0.5">
                      {s.url}
                    </p>
                  </div>
                  <Badge variant={kindVariant(s.type)}>
                    {s.type}
                  </Badge>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="text-xs text-slate-600 dark:text-slate-400">
                    {s.category}
                  </span>
                  <span class="text-slate-300 dark:text-slate-600">
                    &middot;
                  </span>
                  <span
                    class={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full ${PRIORITY_COLORS[s.priority] ?? PRIORITY_COLORS[2]}`}
                  >
                    {PRIORITY_LABELS[s.priority] ??
                      `P${s.priority}`}
                  </span>
                  {s.last_status && (
                    <>
                      <span class="text-slate-300 dark:text-slate-600">
                        &middot;
                      </span>
                      <Badge
                        variant={kindVariant(
                          s.last_status === 'ok'
                            ? 'ok'
                            : 'error',
                        )}
                      >
                        {s.last_status}
                      </Badge>
                    </>
                  )}
                </div>
                <div class="flex items-center justify-between pt-1">
                  <div class="flex items-center gap-2">
                    <ToggleSwitch
                      enabled={s.enabled !== 0}
                      disabled={togglingId === s.id}
                      onChange={() =>
                        handleToggle(s.id, s.enabled ?? 1)
                      }
                    />
                    <span class="text-xs text-slate-500 dark:text-slate-400">
                      {s.enabled !== 0 ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  <Button
                    variant={
                      confirmDeleteId === s.id
                        ? 'danger'
                        : 'ghost'
                    }
                    size="sm"
                    loading={deletingId === s.id}
                    onClick={() => handleDelete(s.id)}
                  >
                    {confirmDeleteId === s.id
                      ? 'Confirm delete'
                      : 'Delete'}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

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

/**
 * Accessible toggle switch. Uses a button with role="switch" so screen
 * readers announce the on/off state correctly.
 */
function ToggleSwitch({
  enabled,
  onChange,
  disabled = false,
}: {
  enabled: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={disabled}
      onClick={onChange}
      class={[
        'relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full',
        'transition-colors duration-200 ease-in-out',
        'focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-1',
        enabled
          ? 'bg-teal-500'
          : 'bg-slate-300 dark:bg-slate-600',
        disabled
          ? 'opacity-50 cursor-not-allowed'
          : 'cursor-pointer',
      ].join(' ')}
    >
      <span
        class={[
          'inline-block h-3.5 w-3.5 rounded-full bg-white shadow',
          'transition-transform duration-200 ease-in-out',
          enabled ? 'translate-x-5' : 'translate-x-0.5',
        ].join(' ')}
      />
    </button>
  );
}
