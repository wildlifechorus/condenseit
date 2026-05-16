import { useState, useEffect, useCallback, useRef } from 'preact/hooks';
import { useSearch } from 'wouter';
import { api } from '../lib/api';
import {
  loadPwaData,
  readPwaRatings,
  writePwaRatings,
  readPwaRead,
  writePwaRead,
  type PwaRatingsStore,
} from '../lib/pwa-data';
import type { DigestDetail, DigestItem } from '../lib/types';
import { DigestCard } from '../components/DigestCard';
import { PwaRatingsToolbar, PwaReadToolbar } from '../components/PwaRatings';
import { PreferencesCard } from '../components/PreferencesCard';
import { FilterPanel } from '../components/FilterPanel';
import { EmptyState } from '../components/EmptyState';
import { Spinner } from '../components/Spinner';
import { Button } from '../components/Button';

/** Map of url -> current saved rating for this digest view. */
type RatingsMap = Record<string, number>;

const IS_PWA = import.meta.env.MODE === 'pwa';

const HEADING_TAGS = new Set(['H1', 'H2', 'H3', 'H4', 'H5', 'H6']);

/**
 * Hide or reveal sections in the formatted prose view that correspond to
 * articles the user has marked as read.
 *
 * Each article in the rendered markdown is expected to start with a heading
 * whose text includes a link to the article URL.  The function finds those
 * anchors, walks up to the enclosing heading, then hides that heading and
 * every following sibling until the next heading at the same or higher level.
 * Also hides any injected `.ci-prose-sep` separator that precedes the heading.
 */
function applyReadFilterToProse(
  prose: HTMLElement,
  readUrls: Set<string>,
): void {
  // Reset previously hidden nodes first (includes injected separators).
  prose
    .querySelectorAll<HTMLElement>('[data-ci-read-hidden]')
    .forEach((el) => {
      el.style.display = '';
      el.removeAttribute('data-ci-read-hidden');
    });

  if (readUrls.size === 0) return;

  const anchors = prose.querySelectorAll<HTMLAnchorElement>('a[href]');
  for (const a of anchors) {
    // Try the raw attribute first, then the browser-resolved absolute URL.
    const rawHref = a.getAttribute('href') ?? '';
    if (!readUrls.has(rawHref) && !readUrls.has(a.href)) continue;

    // Walk up from the anchor to find the nearest heading within the prose.
    let heading: Element | null = a.parentElement;
    while (heading && heading !== prose) {
      if (HEADING_TAGS.has(heading.tagName)) break;
      heading = heading.parentElement;
    }
    if (!heading || !HEADING_TAGS.has(heading.tagName) || heading === prose) {
      continue;
    }

    const level = parseInt(heading.tagName[1], 10);
    const toHide: Element[] = [];

    // Include the injected separator div that sits just before this heading.
    const prev = heading.previousElementSibling;
    if (prev instanceof HTMLElement && prev.classList.contains('ci-prose-sep')) {
      toHide.push(prev);
    }

    toHide.push(heading);
    let sib = heading.nextElementSibling;
    while (sib) {
      if (HEADING_TAGS.has(sib.tagName)) {
        // Stop at a heading that is the same level or higher (smaller number).
        if (parseInt(sib.tagName[1], 10) <= level) break;
      }
      toHide.push(sib);
      sib = sib.nextElementSibling;
    }

    for (const el of toHide) {
      (el as HTMLElement).style.display = 'none';
      (el as HTMLElement).setAttribute('data-ci-read-hidden', '1');
    }
  }
}

/** Attribute added to all elements injected by buildProseControls. */
const PROSE_CTRL_ATTR = 'data-ci-prose-ctrl';

/**
 * Inject per-article visual separators and interactive controls (star rating
 * and mark-read toggle) into the rendered prose HTML.
 *
 * Designed to run immediately before applyReadFilterToProse so that injected
 * elements are present before the read-hide pass runs.
 * Re-runs safely: previously injected elements are removed first.
 */
function buildProseControls(
  prose: HTMLElement,
  readUrls: Set<string>,
  ratings: Record<string, number>,
  onMarkRead: (url: string) => void,
  onRate: (url: string, rating: number) => void,
): void {
  // Remove elements from a previous run.
  prose
    .querySelectorAll(`[${PROSE_CTRL_ATTR}]`)
    .forEach((el) => el.remove());

  // Target headings that contain a direct anchor (article-level headings).
  const headings = prose.querySelectorAll<HTMLElement>(
    'h1,h2,h3,h4,h5,h6',
  );

  for (const heading of headings) {
    const anchor = heading.querySelector<HTMLAnchorElement>('a[href]');
    if (!anchor) continue;
    const url = anchor.getAttribute('href') ?? anchor.href;
    if (!url || url.startsWith('#')) continue;

    const isRead = readUrls.has(url);
    const currentRating = ratings[url] ?? 0;

    // --- Separator injected BEFORE the heading ---
    const sep = document.createElement('div');
    sep.setAttribute(PROSE_CTRL_ATTR, '1');
    sep.className = 'ci-prose-sep';
    heading.parentElement?.insertBefore(sep, heading);

    // --- Control row injected AFTER the heading ---
    const ctrl = document.createElement('div');
    ctrl.setAttribute(PROSE_CTRL_ATTR, '1');
    ctrl.className = 'ci-prose-ctrl';

    // Star buttons (1-5)
    const starsDiv = document.createElement('div');
    starsDiv.className = 'ci-prose-stars';
    for (let star = 1; star <= 5; star++) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.title = `Rate ${star} star${star !== 1 ? 's' : ''}`;
      btn.className = `ci-star-btn${star <= currentRating ? ' active' : ''}`;
      btn.textContent = star <= currentRating ? '★' : '☆';
      const s = star;
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        onRate(url, s);
      });
      starsDiv.appendChild(btn);
    }
    ctrl.appendChild(starsDiv);

    // Mark read / unread button
    const readBtn = document.createElement('button');
    readBtn.type = 'button';
    readBtn.className = `ci-read-btn${isRead ? ' is-read' : ''}`;
    readBtn.innerHTML =
      `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" ` +
      `stroke="currentColor" stroke-width="2.5" stroke-linecap="round" ` +
      `stroke-linejoin="round">` +
      `<path d="M4.5 12.75l6 6 9-13.5"/></svg>` +
      (isRead ? 'Read' : 'Mark read');
    readBtn.title = isRead ? 'Mark as unread' : 'Mark as read';
    readBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      onMarkRead(url);
    });
    ctrl.appendChild(readBtn);

    heading.parentElement?.insertBefore(ctrl, heading.nextSibling);
  }
}

interface DigestPageProps {
  onDigestLoaded?: (id: number | null) => void;
}

/**
 * Digest viewer page.
 * In normal mode fetches from /api/digests; ratings POST to /api/ratings.
 * In PWA mode reads from /digest-data.json; ratings persist to localStorage.
 */
export function DigestPage({ onDigestLoaded }: DigestPageProps) {
  const search = useSearch();
  const params = new URLSearchParams(search);
  const requestedId = params.get('id') ? Number(params.get('id')) : null;
  const showRaw = params.get('raw') === '1';

  const [detail, setDetail] = useState<DigestDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtered, setFiltered] = useState<DigestItem[]>([]);
  const [showProse, setShowProse] = useState(false);

  /**
   * Ratings keyed by URL.
   * In PWA mode: lazy-seeded from localStorage immediately so stars are
   * visible as soon as the cards mount (no async wait required).
   * In normal mode: seeded from the server response in the load effect.
   */
  const [ratings, setRatings] = useState<RatingsMap>(() => {
    if (!IS_PWA) return {};
    return readPwaRatings().byUrl;
  });

  /**
   * Full localStorage ratings store (null in normal mode).
   * Also lazy-initialised so the export toolbar count is correct immediately.
   */
  const [pwaStore, setPwaStore] = useState<PwaRatingsStore | null>(() =>
    IS_PWA ? readPwaRatings() : null,
  );

  /**
   * URLs the user has marked as read, persisted to localStorage.
   * Lazy-initialised so window.localStorage is only accessed in the browser.
   */
  const [readUrls, setReadUrls] = useState<Set<string>>(() => readPwaRead());

  /** When true (default) read items are hidden from the grid. */
  const [hideRead, setHideRead] = useState(true);

  /** Ref for the prose <article> element so we can manipulate its DOM. */
  const proseRef = useRef<HTMLElement | null>(null);

  /**
   * Rebuild per-article prose controls (separator + stars + read toggle) then
   * apply the read-hide filter.  Must run in this order so injected elements
   * are present when applyReadFilterToProse walks siblings.
   * Fires whenever the prose panel opens or any interactive state changes.
   */
  useEffect(() => {
    if (!showProse || !proseRef.current) return;
    const prose = proseRef.current;
    buildProseControls(prose, readUrls, ratings, handleMarkRead, handleRateAndSave);
    applyReadFilterToProse(prose, readUrls);
  }, [showProse, readUrls, ratings, handleMarkRead, handleRateAndSave]);

  useEffect(() => {
    setLoading(true);
    setError(null);

    const load = IS_PWA
      ? loadPwaData()
      : requestedId !== null
        ? api.getDigest(requestedId)
        : api.getLatestDigest();

    load
      .then((d) => {
        setDetail(d);
        setFiltered(d?.items ?? []);
        onDigestLoaded?.(d?.meta.id ?? null);

        if (IS_PWA) {
          // Seed ratings from localStorage for PWA mode.
          const store = readPwaRatings();
          setPwaStore(store);
          const initial: RatingsMap = {};
          for (const item of d?.items ?? []) {
            if (item.url && store.byUrl[item.url] != null) {
              initial[item.url] = store.byUrl[item.url];
            }
          }
          setRatings(initial);
        } else {
          // Seed ratings from the server-supplied per-item ratings.
          const initial: RatingsMap = {};
          for (const item of d?.items ?? []) {
            if (item.url && item.rating != null) {
              initial[item.url] = item.rating;
            }
          }
          setRatings(initial);

          // Sync read URLs from the server; merge with any pre-existing
          // localStorage entries so the UI is immediately consistent.
          api
            .getReadUrls()
            .then(({ urls }) => {
              setReadUrls((prev) => {
                const merged = new Set([...prev, ...urls]);
                writePwaRead(merged);
                return merged;
              });
            })
            .catch(() => {
              // Best-effort: fall back to whatever localStorage had.
            });
        }
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load digest.');
      })
      .finally(() => setLoading(false));
  }, [requestedId]);

  /** Update ratings after a card-level save. PWA path also persists to localStorage. */
  const handleRate = useCallback(
    (url: string, rating: number) => {
      setRatings((prev) => ({ ...prev, [url]: rating }));
      if (IS_PWA) {
        setPwaStore((prev) => {
          const next: PwaRatingsStore = {
            v: 1,
            byUrl: { ...(prev?.byUrl ?? {}), [url]: rating },
          };
          writePwaRatings(next);
          return next;
        });
      }
    },
    [],
  );

  /** PWA handler passed to DigestCard: saves to localStorage directly. */
  const pwaRate = IS_PWA ? handleRate : undefined;

  /**
   * Used by the prose controls: updates state (and localStorage in PWA mode)
   * AND submits to the server in hosted mode.
   * Mirrors what DigestCard does internally for card-level ratings.
   */
  const handleRateAndSave = useCallback(
    (url: string, rating: number) => {
      handleRate(url, rating);
      if (!IS_PWA) {
        api.submitRating(url, rating).catch(() => undefined);
      }
    },
    [handleRate],
  );

  /**
   * Toggle the read state for a URL.
   * Always persists to localStorage for immediate UI feedback.
   * In non-PWA mode also calls the server so the next digest pipeline
   * can exclude articles the user has already read.
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
      writePwaRead(next);
      if (!IS_PWA) {
        // Best-effort server persist; UI is already updated locally.
        api.markRead(url, nowRead).catch(() => undefined);
      }
      return next;
    });
  }, []);

  const handleFiltered = useCallback((items: DigestItem[]) => {
    setFiltered(items);
  }, []);

  if (showRaw && detail) {
    return (
      <pre class="text-xs font-mono text-slate-700 dark:text-slate-300 whitespace-pre-wrap break-words p-4">
        {detail.html}
      </pre>
    );
  }

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
          !IS_PWA ? (
            <a href="/admin/sources" class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors">
              Configure sources
            </a>
          ) : undefined
        }
        icon={
          <svg class="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
        }
      />
    );
  }

  const { meta, html, items } = detail;
  const hasItems = items.length > 0;
  const ratedCount = Object.keys(ratings).length;

  /** Items that pass the FilterPanel criteria. */
  const readCount = filtered.filter((i) => readUrls.has(i.url)).length;

  /** Items shown in the grid, optionally excluding read ones. */
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
        {!IS_PWA && (
          <a
            href={`/?id=${meta.id}&raw=1`}
            class="text-xs text-slate-400 dark:text-slate-500 hover:text-teal-600 dark:hover:text-teal-400 transition-colors"
          >
            View source
          </a>
        )}
      </div>

      {/* Card browser */}
      {hasItems && (
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
          <FilterPanel items={items} onFiltered={handleFiltered} />

          <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-4 flex-wrap">
            <p class="text-xs text-slate-500 dark:text-slate-400">
              {visibleItems.length === items.length
                ? `${items.length} item${items.length !== 1 ? 's' : ''}`
                : `${visibleItems.length} of ${items.length} item${items.length !== 1 ? 's' : ''}`}
            </p>
            {readCount > 0 && (
              <button
                type="button"
                onClick={() => setHideRead((h) => !h)}
                class="text-xs text-slate-400 dark:text-slate-500 hover:text-teal-600 dark:hover:text-teal-400 transition-colors"
              >
                {hideRead
                  ? `${readCount} read item${readCount !== 1 ? 's' : ''} hidden`
                  : 'Hide read items'}
              </button>
            )}
          </div>

          {visibleItems.length === 0 ? (
            <div class="py-10 text-center text-sm text-slate-500 dark:text-slate-400">
              {readCount > 0 && hideRead
                ? 'All matching items are marked as read.'
                : 'No items match these filters.'}
            </div>
          ) : (
            <div class="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              {visibleItems.map((item) => (
                <DigestCard
                  key={item.url}
                  item={{ ...item, rating: ratings[item.url] ?? item.rating }}
                  onRate={IS_PWA ? pwaRate : handleRate}
                  onMarkRead={handleMarkRead}
                  isRead={readUrls.has(item.url)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Prose fallback (full formatted digest) */}
      {html && (
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
          {hasItems ? (
            <>
              <button
                type="button"
                onClick={() => setShowProse((s) => !s)}
                class="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-teal-600 dark:text-teal-400 bg-slate-50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                {showProse ? 'Hide' : 'Show'} full formatted digest
                <svg class={`w-4 h-4 transition-transform ${showProse ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showProse && (
                <article
                  ref={proseRef}
                  class="prose px-6 py-5 max-w-none"
                  dangerouslySetInnerHTML={{ __html: html }}
                />
              )}
            </>
          ) : (
            <article
              class="prose px-6 py-5 max-w-none"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>
      )}

      {/* PWA: download toolbar appears once any item is rated */}
      {IS_PWA && pwaStore && (
        <PwaRatingsToolbar
          store={pwaStore}
          digestId={meta.id ?? 0}
          ratedCount={ratedCount}
        />
      )}

      {/* PWA: download toolbar appears once any item is marked as read */}
      {IS_PWA && (
        <PwaReadToolbar readUrls={readUrls} />
      )}

      {/* Normal mode: collapsible preferences card */}
      {!IS_PWA && <PreferencesCard />}
    </div>
  );
}
