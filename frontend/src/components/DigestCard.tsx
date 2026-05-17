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
  /** Opens the detail panel for this item. */
  onSelect?: (item: DigestItem) => void;
  /** Called when the user clicks "Read Later" to toggle save state. */
  onReadLater?: (item: DigestItem) => void;
  /** Whether this item is currently saved to read later. */
  isReadLater?: boolean;
  /**
   * Called when the user dismisses this card. Typically marks the item as
   * read so it disappears from the default (hide-read) view.
   */
  onDismiss?: (url: string) => void;
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
  onSelect,
  onReadLater,
  isReadLater = false,
  onDismiss,
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
  const [readLaterFlash, setReadLaterFlash] = useState(false);

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

      {/* Dismiss button: top-right corner, icon-only, does not add to the
          bottom-bar clutter and works equally well on touch devices. */}
      {onDismiss && !isRead && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss(item.url);
          }}
          title='Dismiss'
          aria-label='Dismiss this item'
          class={[
            'absolute top-2 right-2 p-1.5 rounded-md',
            'text-slate-300 dark:text-slate-600',
            'hover:text-slate-500 dark:hover:text-slate-400',
            'hover:bg-slate-100 dark:hover:bg-slate-800',
            'transition-colors',
          ].join(' ')}
        >
          <svg
            class='w-3.5 h-3.5'
            viewBox='0 0 24 24'
            fill='none'
            stroke='currentColor'
            stroke-width='2.5'
          >
            <path
              stroke-linecap='round'
              stroke-linejoin='round'
              d='M6 18L18 6M6 6l12 12'
            />
          </svg>
        </button>
      )}

      <div class="flex items-center gap-2 flex-wrap">
        <Badge variant={kindVariant(item.kind)}>{item.kind}</Badge>
        {item.category && (
          <span class="text-xs text-slate-500 dark:text-slate-400 font-medium">
            {item.category}
          </span>
        )}
      </div>

      <h3 class="text-sm font-semibold text-slate-900 dark:text-slate-100 leading-snug">
        {/*
         * When a detail panel is available, left-click opens it.
         * The href is still present so right-click / middle-click opens the
         * source URL directly in a new tab.
         */}
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={
            onSelect
              ? (e) => {
                  e.preventDefault();
                  onSelect(item);
                }
              : undefined
          }
          class={[
            'transition-colors',
            onSelect
              ? 'cursor-pointer hover:text-teal-600 dark:hover:text-teal-400'
              : 'hover:text-teal-600 dark:hover:text-teal-400',
          ].join(' ')}
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
        <p
          class={[
            'text-sm text-slate-600 dark:text-slate-400 leading-relaxed line-clamp-4',
            onSelect ? 'cursor-pointer' : '',
          ].join(' ')}
          onClick={onSelect ? () => onSelect(item) : undefined}
        >
          {summary}
        </p>
      )}

      {item.url && (
        <div class="mt-1 pt-2 border-t border-slate-100 dark:border-slate-800 overflow-x-auto pb-1">
          <div class="flex w-max min-w-full items-center gap-2">
            <div class="flex items-center gap-1.5 shrink-0">
              {onReadLater && (
                <button
                  type="button"
                  onClick={() => {
                    onReadLater(item);
                    if (!isReadLater) {
                      setReadLaterFlash(true);
                      setTimeout(() => setReadLaterFlash(false), 2000);
                    }
                  }}
                  title={
                    isReadLater ? 'Remove from Read Later' : 'Save to Read Later'
                  }
                  class={[
                    'flex items-center gap-1 text-xs px-2 py-1 rounded-md border',
                    'transition-colors',
                    isReadLater
                      ? 'border-amber-200 dark:border-amber-800 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20'
                      : readLaterFlash
                        ? 'border-amber-300 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20'
                        : 'border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:border-amber-300 hover:text-amber-600 dark:hover:text-amber-400',
                  ].join(' ')}
                >
                  <svg
                    class="w-3 h-3"
                    fill={isReadLater ? 'currentColor' : 'none'}
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
                    />
                  </svg>
                  {isReadLater ? 'Saved' : 'Read later'}
                </button>
              )}

              {onMarkRead && (
                <button
                  type="button"
                  onClick={() => onMarkRead(item.url)}
                  title={isRead ? 'Mark as unread' : 'Mark as read'}
                  class={[
                    'flex items-center gap-1 text-xs px-2 py-1 rounded-md border',
                    'transition-colors',
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

            <div class="ml-auto flex items-center gap-2 shrink-0">
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
          </div>
        </div>
      )}
    </article>
  );
}
