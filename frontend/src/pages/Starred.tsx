import { useState, useEffect, useCallback } from 'preact/hooks';
import { api } from '../lib/api';
import type { DigestItem, StarredItem } from '../lib/types';
import { normalizeItem } from '../lib/normalize-item';
import { DigestCard } from '../components/DigestCard';
import { ItemDetailPanel } from '../components/ItemDetailPanel';
import { EmptyState } from '../components/EmptyState';
import { Spinner } from '../components/Spinner';

type RatingsMap = Record<string, number>;

/**
 * Page that shows all items the user has starred for permanent keeping.
 * Items remain here until explicitly unstarred. Starring is independent
 * of Read Later and digest runs.
 */
export function StarredPage() {
  const [items, setItems] = useState<StarredItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [ratings, setRatings] = useState<RatingsMap>({});
  const [starredUrls, setStarredUrls] = useState<Set<string>>(new Set());
  const [readLaterUrls, setReadLaterUrls] = useState<Set<string>>(new Set());
  const [selectedItem, setSelectedItem] = useState<DigestItem | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.getStarredItems(),
      api.getReadLaterUrls().catch((): { urls: string[] } => ({ urls: [] })),
    ])
      .then(([{ items: fetched }, { urls: rlUrls }]) => {
        setItems(fetched);
        setStarredUrls(new Set(fetched.map((i) => i.url)));
        setReadLaterUrls(new Set(rlUrls));

        const initial: RatingsMap = {};
        for (const item of fetched) {
          if (item.url && item.rating != null) {
            initial[item.url] = item.rating;
          }
        }
        setRatings(initial);
      })
      .catch((e: unknown) => {
        setError(
          e instanceof Error ? e.message : 'Failed to load starred items.',
        );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRate = useCallback((url: string, rating: number) => {
    setRatings((prev) => ({ ...prev, [url]: rating }));
  }, []);

  /** Unstarring removes the item from this page entirely. */
  const handleUnstar = useCallback(
    (url: string) => {
      setItems((prev) => prev.filter((i) => i.url !== url));
      setStarredUrls((prev) => {
        const next = new Set(prev);
        next.delete(url);
        return next;
      });
      if (selectedItem?.url === url) {
        setSelectedItem(null);
      }
      api.unstarItem(url).catch(() => undefined);
    },
    [selectedItem],
  );

  const handleToggleStar = useCallback(
    (item: DigestItem) => {
      if (starredUrls.has(item.url)) {
        handleUnstar(item.url);
      } else {
        setStarredUrls((prev) => new Set([...prev, item.url]));
        api.starItem(item).catch(() => undefined);
      }
    },
    [starredUrls, handleUnstar],
  );

  const handleReadLaterToggle = useCallback((item: DigestItem) => {
    const url = item.url;
    setReadLaterUrls((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
        api.removeReadLater(url).catch(() => undefined);
      } else {
        next.add(url);
        api.saveReadLater(item).catch(() => undefined);
      }
      return next;
    });
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
        title="Could not load starred items"
        description={error}
        action={
          <button
            type="button"
            onClick={load}
            class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
          >
            Retry
          </button>
        }
        icon={
          <svg
            class="w-10 h-10"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
        }
      />
    );
  }

  if (items.length === 0) {
    return (
      <div class="space-y-4">
        <div>
          <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Starred
          </h1>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Articles you want to keep forever.
          </p>
        </div>

        <EmptyState
          title="Nothing starred yet"
          description="Hit the Star button on any digest item to save it here permanently. Starred items stay forever until you unstar them."
          icon={
            <svg
              class="w-10 h-10"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="1.5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
              />
            </svg>
          }
          action={
            <a
              href="/"
              class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
            >
              Go to digest
            </a>
          }
        />
      </div>
    );
  }

  return (
    <div class="space-y-4">
      {/* Page header */}
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Starred
          </h1>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {items.length} item{items.length !== 1 ? 's' : ''} starred -
            unstar to remove
          </p>
        </div>
      </div>

      {/* Item grid */}
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
          <svg
            class="w-4 h-4 text-yellow-500 dark:text-yellow-400 flex-shrink-0"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
            />
          </svg>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            These items are saved permanently and are not affected by new digest
            runs. Unstar to remove.
          </p>
        </div>

        <div class="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((raw) => {
            const item = normalizeItem({
              ...raw,
              rating: ratings[raw.url] ?? raw.rating,
            });
            return (
              <DigestCard
                key={item.url}
                item={item}
                onRate={handleRate}
                onSelect={setSelectedItem}
                onToggleStar={handleToggleStar}
                isStarred={starredUrls.has(item.url)}
                onReadLater={handleReadLaterToggle}
                isReadLater={readLaterUrls.has(item.url)}
              />
            );
          })}
        </div>
      </div>

      {/* Detail panel */}
      {selectedItem && (
        <ItemDetailPanel
          item={normalizeItem({
            ...selectedItem,
            rating: ratings[selectedItem.url] ?? selectedItem.rating,
          })}
          isRead={false}
          rating={ratings[selectedItem.url] ?? selectedItem.rating}
          onClose={() => setSelectedItem(null)}
          onRate={handleRate}
          onToggleStar={handleToggleStar}
          isStarred={starredUrls.has(selectedItem.url)}
          onReadLater={handleReadLaterToggle}
          isReadLater={readLaterUrls.has(selectedItem.url)}
        />
      )}
    </div>
  );
}
