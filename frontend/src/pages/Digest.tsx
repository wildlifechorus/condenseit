import { useState, useEffect, useCallback } from 'preact/hooks';
import { useSearch } from 'wouter';
import { api } from '../lib/api';
import type { DigestDetail, DigestItem } from '../lib/types';
import { normalizeItem } from '../lib/normalize-item';
import { DigestCard } from '../components/DigestCard';
import { ItemDetailPanel } from '../components/ItemDetailPanel';
import { FilterPanel } from '../components/FilterPanel';
import { EmptyState } from '../components/EmptyState';
import { Spinner } from '../components/Spinner';
import { Button } from '../components/Button';

/** Map of url -> current saved rating for this digest view. */
type RatingsMap = Record<string, number>;

interface DigestPageProps {
  onDigestLoaded?: (id: number | null) => void;
}

/** Digest viewer page. Fetches from /api/digests; ratings POST to /api/ratings. */
export function DigestPage({ onDigestLoaded }: DigestPageProps) {
  const search = useSearch();
  const params = new URLSearchParams(search);
  const requestedId = params.get('id') ? Number(params.get('id')) : null;

  const [detail, setDetail] = useState<DigestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtered, setFiltered] = useState<DigestItem[]>([]);

  /** Ratings keyed by URL, seeded from server response. */
  const [ratings, setRatings] = useState<RatingsMap>({});

  /** URLs the user has marked as read. */
  const [readUrls, setReadUrls] = useState<Set<string>>(new Set());

  /** When true (default) read items are hidden from the grid. */
  const [hideRead, setHideRead] = useState(true);

  /** Item currently open in the detail panel, or null when closed. */
  const [selectedItem, setSelectedItem] = useState<DigestItem | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const load =
      requestedId !== null
        ? api.getDigest(requestedId)
        : api.getLatestDigest();

    load
      .then((d) => {
        setDetail(d);
        setFiltered(d?.items ?? []);
        onDigestLoaded?.(d?.meta.id ?? null);

        // Seed ratings from server-supplied per-item ratings.
        const initial: RatingsMap = {};
        for (const item of d?.items ?? []) {
          if (item.url && item.rating != null) {
            initial[item.url] = item.rating;
          }
        }
        setRatings(initial);

        // Fetch read state from server.
        api
          .getReadUrls()
          .then(({ urls }) => setReadUrls(new Set(urls)))
          .catch(() => {});
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load digest.');
      })
      .finally(() => setLoading(false));
  }, [requestedId]);

  /** Update ratings after a card-level save. */
  const handleRate = useCallback((url: string, rating: number) => {
    setRatings((prev) => ({ ...prev, [url]: rating }));
  }, []);

  /**
   * Toggle the read state for a URL.
   * Calls the server so the next digest pipeline can exclude articles
   * the user has already read.
   */
  const handleMarkRead = useCallback((url: string) => {
    setReadUrls((prev) => {
      const next = new Set(prev);
      const nowRead = !next.has(url);
      if (nowRead) {
        next.add(url);
      } else {
        next.delete(url);
      }
      api.markRead(url, nowRead).catch(() => undefined);
      return next;
    });
  }, []);

  const handleFiltered = useCallback((items: DigestItem[]) => {
    setFiltered(items);
  }, []);

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        title="Could not load digest"
        description={error}
        action={
          <Button onClick={() => window.location.reload()}>Retry</Button>
        }
        icon={
          <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        }
      />
    );
  }

  if (!detail) {
    return (
      <EmptyState
        title="No digest yet"
        description="Click Run digest in the header to generate one, or configure your sources first."
        action={
          <a href="/admin/sources" class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors">
            Configure sources
          </a>
        }
        icon={
          <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        }
      />
    );
  }

  const { meta, items } = detail;
  const hasItems = items.length > 0;

  const readCount = filtered.filter((i) => readUrls.has(i.url)).length;

  const visibleItems = hideRead
    ? filtered.filter((i) => !readUrls.has(i.url))
    : filtered;

  return (
    <div class="space-y-4">
      {/* Page header */}
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Digest #{meta.id}
          </h1>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {meta.created_at?.slice(0, 16).replace('T', ' ')} UTC
            {meta.articles_count != null && ` · ${meta.articles_count} articles`}
            {meta.model && ` · ${meta.model}`}
            {meta.processing_time && ` · ${meta.processing_time}`}
          </p>
        </div>
      </div>

      {/* Card browser */}
      {hasItems && (
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
          <FilterPanel
            items={items}
            onFiltered={handleFiltered}
            readCount={readCount}
            hideRead={hideRead}
            onToggleHideRead={() => setHideRead((h) => !h)}
          />

          <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-4 flex-wrap">
            <p class="text-xs text-slate-500 dark:text-slate-400">
              {visibleItems.length === items.length
                ? `${items.length} item${items.length !== 1 ? 's' : ''}`
                : `${visibleItems.length} of ${items.length} item${items.length !== 1 ? 's' : ''}`}
            </p>
          </div>

          {visibleItems.length === 0 ? (
            <div class="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
              {readCount > 0 && hideRead
                ? 'All matching items are marked as read.'
                : 'No items match these filters.'}
            </div>
          ) : (
            <div class="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {visibleItems.map((raw) => {
                const item = normalizeItem({
                  ...raw,
                  rating: ratings[raw.url] ?? raw.rating,
                });
                return (
                  <DigestCard
                    key={item.url}
                    item={item}
                    onRate={handleRate}
                    onMarkRead={handleMarkRead}
                    isRead={readUrls.has(item.url)}
                    onSelect={setSelectedItem}
                  />
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Item detail panel (slide-over) */}
      {selectedItem && (
        <ItemDetailPanel
          item={normalizeItem({
            ...selectedItem,
            rating: ratings[selectedItem.url] ?? selectedItem.rating,
          })}
          isRead={readUrls.has(selectedItem.url)}
          rating={ratings[selectedItem.url] ?? selectedItem.rating}
          onClose={() => setSelectedItem(null)}
          onRate={handleRate}
          onMarkRead={handleMarkRead}
        />
      )}
    </div>
  );
}
