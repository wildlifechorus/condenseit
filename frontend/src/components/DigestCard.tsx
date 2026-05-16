import { useState, useEffect } from 'preact/hooks';
import { Badge, kindVariant } from './Badge';
import { RatingStars } from './RatingStars';
import { cleanSummary } from '../lib/clean-summary';
import type { DigestItem } from '../lib/types';
import { api } from '../lib/api';

interface DigestCardProps {
  item: DigestItem;
  /** Called with (url, newRating) after a successful save so the parent can
   *  update its own state map. */
  onRate?: (url: string, rating: number) => void;
  /** Called with the item URL to toggle its read state. */
  onMarkRead?: (url: string) => void;
  /** Whether this item has been marked as read. */
  isRead?: boolean;
}

function formatDate(iso?: string): string {
  if (!iso) return '';
  const d = iso.slice(0, 10);
  try {
    return new Date(d).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
    });
  } catch {
    return d;
  }
}

/**
 * Single article / video / watch card with title, summary,
 * category badge, source, published date, inline star rating,
 * and a mark-as-read toggle.
 */
export function DigestCard({
  item,
  onRate,
  onMarkRead,
  isRead = false,
}: DigestCardProps) {
  const summary = cleanSummary(item.summary);
  const metaParts: string[] = [];
  if (item.source) metaParts.push(item.source);
  const date = formatDate(item.published_at);
  if (date) metaParts.push(date);

  /** Local rating mirrors the parent map so the stars feel instant. */
  const [localRating, setLocalRating] = useState<number | null>(
    item.rating ?? null,
  );
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  /**
   * Sync local star display whenever the parent updates item.rating
   * (e.g. after localStorage or API ratings are loaded post-mount).
   */
  useEffect(() => {
    setLocalRating(item.rating ?? null);
  }, [item.rating]);

  async function handleRate(rating: number) {
    if (saving) return;
    setLocalRating(rating);
    setSaving(true);
    try {
      await api.submitRating(item.url, rating);
      onRate?.(item.url, rating);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch {
      /* best-effort: star UI stays updated even if the network call fails */
    } finally {
      setSaving(false);
    }
  }

  return (
    <article
      class={[
        'relative flex flex-col gap-2 bg-white dark:bg-slate-900 rounded-xl p-4 pl-5 transition-shadow overflow-hidden',
        isRead
          ? 'border border-slate-100 dark:border-slate-800 shadow-sm opacity-55 hover:opacity-80'
          : 'border border-slate-200 dark:border-slate-700 shadow hover:shadow-md',
      ].join(' ')}
    >
      {/* Left accent strip acts as a clear visual start-of-card marker */}
      <div
        class={[
          'absolute inset-y-0 left-0 w-1',
          isRead
            ? 'bg-teal-200 dark:bg-teal-800'
            : 'bg-teal-400 dark:bg-teal-500',
        ].join(' ')}
      />

      <div class="flex items-center gap-2 flex-wrap">
        <Badge variant={kindVariant(item.kind)}>{item.kind}</Badge>
        {item.category && (
          <span class="text-xs text-slate-500 dark:text-slate-400 font-medium">
            {item.category}
          </span>
        )}
      </div>

      <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100 leading-snug">
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          class="hover:text-teal-600 dark:hover:text-teal-400 transition-colors"
        >
          {item.title || 'Untitled'}
        </a>
      </h3>

      {metaParts.length > 0 && (
        <p class="text-xs text-slate-400 dark:text-slate-500">
          {metaParts.join(' · ')}
        </p>
      )}

      {summary && (
        <p class="text-sm text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-4">
          {summary}
        </p>
      )}

      {item.url && (
        <div class="flex items-center justify-between gap-2 mt-1 pt-2 border-t border-slate-100 dark:border-slate-800">
          <div class="flex items-center gap-2">
            <RatingStars
              value={localRating}
              onChange={handleRate}
              disabled={saving}
            />
            {savedFlash && (
              <span class="text-xs text-teal-600 dark:text-teal-400 font-medium">
                Saved
              </span>
            )}
          </div>

          {onMarkRead && (
            <button
              type="button"
              onClick={() => onMarkRead(item.url)}
              title={isRead ? 'Mark as unread' : 'Mark as read'}
              class={[
                'flex items-center gap-1 text-xs px-2 py-1 rounded-md border',
                'transition-colors shrink-0',
                isRead
                  ? 'border-teal-200 dark:border-teal-800 text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/20'
                  : 'border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:border-teal-300 hover:text-teal-600 dark:hover:text-teal-400',
              ].join(' ')}
            >
              <svg
                class="w-3 h-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2.5"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M4.5 12.75l6 6 9-13.5"
                />
              </svg>
              {isRead ? 'Read' : 'Mark read'}
            </button>
          )}
        </div>
      )}
    </article>
  );
}
