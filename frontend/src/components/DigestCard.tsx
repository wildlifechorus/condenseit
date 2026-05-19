import { useState, useEffect } from 'preact/hooks';
import { Badge, kindVariant } from './Badge';
import { RatingStars } from './RatingStars';
import { cleanSummary } from '../lib/clean-summary';
import type { DigestItem, ScoreBreakdown } from '../lib/types';
import { api } from '../lib/api';

/** Human-readable labels for each score signal. */
const SIGNAL_LABELS: Record<string, string> = {
  keyword_high: 'Keyword (high)',
  keyword_medium: 'Keyword (medium)',
  term_overlap: 'Topic terms',
  bigram_overlap: 'Topic phrases',
  tfidf_cosine: 'Content similarity',
  category: 'Category',
  source: 'Source',
  implicit_content: 'Read/saved content',
  implicit_category: 'Read/saved category',
  implicit_source: 'Read/saved source',
  synonym_boost: 'Related topics',
  embedding_similarity: 'Semantic similarity',
  topic_score: 'Topic match',
  llm_rerank: 'AI relevance',
};

/** Collapsible score breakdown panel shown at the bottom of each card. */
function ScoreBreakdownPanel({ breakdown }: { breakdown: ScoreBreakdown }) {
  const [open, setOpen] = useState(false);
  const nonZero = Object.entries(breakdown).filter(
    ([k, v]) => k !== 'llm_reason' && typeof v === 'number' && Math.abs(v as number) > 0.001,
  ) as [string, number][];

  if (nonZero.length === 0) return null;

  const maxAbs = Math.max(...nonZero.map(([, v]) => Math.abs(v as number)), 0.1);
  const llmReason = breakdown.llm_reason;

  return (
    <div class="pt-1">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        class="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
      >
        <svg
          class={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="2.5"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M8.25 4.5l7.5 7.5-7.5 7.5"
          />
        </svg>
        Why ranked here?
      </button>
      {open && (
        <div class="mt-2 space-y-1.5">
          {nonZero.map(([key, val]) => {
            const pct = (Math.abs(val) / maxAbs) * 100;
            const isPos = val >= 0;
            const label = SIGNAL_LABELS[key] ?? key;
            return (
              <div key={key} class="flex items-center gap-2">
                <span class="text-xs text-slate-500 dark:text-slate-400 w-32 flex-shrink-0 truncate">
                  {label}
                </span>
                <div class="flex-1 flex items-center gap-1">
                  <div class="flex-1 bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      class={`h-1.5 rounded-full ${isPos ? 'bg-teal-400 dark:bg-teal-500' : 'bg-rose-400 dark:bg-rose-500'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span
                    class={`text-xs font-mono w-10 text-right flex-shrink-0 ${isPos ? 'text-teal-600 dark:text-teal-400' : 'text-rose-500 dark:text-rose-400'}`}
                  >
                    {isPos ? '+' : ''}
                    {val.toFixed(2)}
                  </span>
                </div>
              </div>
            );
          })}
          {llmReason && (
            <p class="text-xs text-slate-400 dark:text-slate-500 italic pt-0.5">
              AI: {llmReason}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

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
  /** Called when the user toggles the starred state of this item. */
  onToggleStar?: (item: DigestItem) => void;
  /** Whether this item is currently starred. */
  isStarred?: boolean;
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
  onToggleStar,
  isStarred = false,
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
  const [starFlash, setStarFlash] = useState(false);

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

      <div class="flex items-start gap-3">
        <div class="flex-1 min-w-0">
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
            <p class="mt-1 text-xs text-slate-400 dark:text-slate-500">
              {metaParts.join(' · ')}
            </p>
          )}
        </div>

        {item.image_url && (
          <img
            src={item.image_url}
            alt=""
            loading="lazy"
            class="flex-shrink-0 w-20 h-20 rounded-md object-cover bg-slate-100 dark:bg-slate-800"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = 'none';
            }}
          />
        )}
      </div>

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

      {item.relevance_to_you && (
        <p class="text-xs text-teal-700 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/20 rounded px-2 py-1 leading-relaxed">
          {item.relevance_to_you}
        </p>
      )}

      {item.topics && item.topics.length > 0 && (
        <div class="flex flex-wrap gap-1">
          {item.topics.slice(0, 5).map((t) => (
            <span
              key={t}
              class="text-xs px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400"
            >
              {t}
            </span>
          ))}
          {item.novelty !== undefined && item.novelty >= 4 && (
            <span class="text-xs px-1.5 py-0.5 rounded-full bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 font-medium">
              novel
            </span>
          )}
        </div>
      )}

      {item.score_breakdown && (
        <ScoreBreakdownPanel breakdown={item.score_breakdown} />
      )}

      {item.url && (
        <div class="mt-1 pt-2 border-t border-slate-100 dark:border-slate-800 overflow-x-auto pb-1">
          <div class="flex w-max min-w-full items-center gap-2">
            <div class="flex items-center gap-1.5 shrink-0">
              {onToggleStar && (
                <button
                  type="button"
                  onClick={() => {
                    onToggleStar(item);
                    if (!isStarred) {
                      setStarFlash(true);
                      setTimeout(() => setStarFlash(false), 2000);
                    }
                  }}
                  title={isStarred ? 'Unstar this item' : 'Star to save forever'}
                  class={[
                    'flex items-center gap-1 text-xs px-2 py-1 rounded-md border',
                    'transition-colors',
                    isStarred
                      ? 'border-yellow-300 dark:border-yellow-700 text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20'
                      : starFlash
                        ? 'border-yellow-300 text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20'
                        : 'border-slate-200 dark:border-slate-700 text-slate-400 dark:text-slate-500 hover:border-yellow-300 hover:text-yellow-600 dark:hover:text-yellow-400',
                  ].join(' ')}
                >
                  <svg
                    class="w-3 h-3"
                    fill={isStarred ? 'currentColor' : 'none'}
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
                    />
                  </svg>
                  {isStarred ? 'Starred' : 'Star'}
                </button>
              )}

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
