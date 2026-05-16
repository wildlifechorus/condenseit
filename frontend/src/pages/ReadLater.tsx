import { useState, useEffect, useCallback } from 'preact/hooks';
import { api } from '../lib/api';
import type { DigestItem, ReadLaterItem } from '../lib/types';
import { normalizeItem } from '../lib/normalize-item';
import { DigestCard } from '../components/DigestCard';
import { ItemDetailPanel } from '../components/ItemDetailPanel';
import { EmptyState } from '../components/EmptyState';
import { Spinner } from '../components/Spinner';

/** Map of url -> star rating for the read-later list view. */
type RatingsMap = Record<string, number>;

/**
 * Page that shows all items the user has saved to read later.
 * Items persist here until explicitly dismissed (marked as read / removed).
 * This list is independent of digest generation - new digest runs do NOT
 * clear it.
 */
export function ReadLaterPage() {
  const [items, setItems] = useState<ReadLaterItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /** Ratings keyed by URL, seeded from server response. */
  const [ratings, setRatings] = useState<RatingsMap>({});

  /** URLs in this list - all items here are by definition "read later". */
  const [readLaterUrls, setReadLaterUrls] = useState<Set<string>>(new Set());

  /** Item currently open in the detail panel. */
  const [selectedItem, setSelectedItem] = useState<DigestItem | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getReadLaterItems()
      .then(({ items: fetched }) => {
        setItems(fetched);
        setReadLaterUrls(new Set(fetched.map((i) => i.url)));

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
          e instanceof Error ? e.message : 'Failed to load read-later list.',
        );
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** Update ratings after a card-level save. */
  const handleRate = useCallback((url: string, rating: number) => {
    setRatings((prev) => ({ ...prev, [url]: rating }));
  }, []);

  /**
   * Removing from read-later: deletes the item from this list entirely.
   * This is the primary action on this page ("mark as done / read").
   */
  const handleRemove = useCallback((url: string) => {
    setItems((prev) => prev.filter((i) => i.url !== url));
    setReadLaterUrls((prev) => {
      const next = new Set(prev);
      next.delete(url);
      return next;
    });
    if (selectedItem?.url === url) {
      setSelectedItem(null);
    }
    api.removeReadLater(url).catch(() => undefined);
  }, [selectedItem]);

  /**
   * Handler passed to DigestCard / ItemDetailPanel as `onReadLater`.
   * On this page toggling = removing (the item is already saved here).
   */
  const handleReadLaterToggle = useCallback((item: DigestItem) => {
    handleRemove(item.url);
  }, [handleRemove]);

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
        title="Could not load read-later list"
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
            Read Later
          </h1>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Items you save here stay until you mark them as done.
          </p>
        </div>

        <EmptyState
          title="Nothing saved yet"
          description='Hit the bookmark button on any digest item to save it here for later. Items stay until you remove them, even after new digest runs.'
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
                d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
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
            Read Later
          </h1>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {items.length} item{items.length !== 1 ? 's' : ''} saved ·
            click bookmark or &quot;Mark done&quot; to remove
          </p>
        </div>
      </div>

      {/* Item grid */}
      <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
        <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center gap-3">
          <svg
            class="w-4 h-4 text-amber-500 dark:text-amber-400 flex-shrink-0"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
            />
          </svg>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            These items persist independently of new digest runs. Remove them
            when you&apos;re done.
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
                onReadLater={handleReadLaterToggle}
                isReadLater={readLaterUrls.has(item.url)}
                /*
                 * "Mark read" on this page means "I'm done, remove it".
                 * We reuse onMarkRead for that action so the familiar
                 * checkmark button still works.
                 */
                onMarkRead={handleRemove}
                isRead={false}
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
          onMarkRead={handleRemove}
          onReadLater={handleReadLaterToggle}
          isReadLater={readLaterUrls.has(selectedItem.url)}
        />
      )}
    </div>
  );
}
