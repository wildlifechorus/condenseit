import type { DigestDetail } from './types';

/**
 * Load static digest data when running as a deployed PWA.
 * The file is written by condenseit pwa-build alongside the app bundle.
 */
export async function loadPwaData(): Promise<DigestDetail | null> {
  try {
    const res = await fetch('/digest-data.json', { cache: 'no-cache' });
    if (!res.ok) return null;
    return (await res.json()) as DigestDetail;
  } catch {
    return null;
  }
}

/** localStorage key for PWA ratings. */
export const PWA_RATINGS_LS_KEY = 'condenseit_pwa_ratings_v1';

export interface PwaRatingsStore {
  v: number;
  byUrl: Record<string, number>;
}

export function readPwaRatings(): PwaRatingsStore {
  try {
    const raw = window.localStorage.getItem(PWA_RATINGS_LS_KEY);
    if (!raw) return { v: 1, byUrl: {} };
    const o = JSON.parse(raw) as PwaRatingsStore;
    if (!o || typeof o !== 'object' || typeof o.byUrl !== 'object') {
      return { v: 1, byUrl: {} };
    }
    return { v: 1, byUrl: o.byUrl };
  } catch {
    return { v: 1, byUrl: {} };
  }
}

export function writePwaRatings(store: PwaRatingsStore): void {
  window.localStorage.setItem(PWA_RATINGS_LS_KEY, JSON.stringify(store));
}

/** localStorage key for PWA read-item tracking. */
export const PWA_READ_LS_KEY = 'condenseit_pwa_read_v1';

interface PwaReadStore {
  v: number;
  urls: string[];
}

/**
 * Read the set of URLs the user has marked as read from localStorage.
 * Returns an empty Set when the key is missing or malformed.
 */
export function readPwaRead(): Set<string> {
  try {
    const raw = window.localStorage.getItem(PWA_READ_LS_KEY);
    if (!raw) return new Set();
    const o = JSON.parse(raw) as PwaReadStore;
    if (!o || !Array.isArray(o.urls)) return new Set();
    return new Set(o.urls);
  } catch {
    return new Set();
  }
}

/**
 * Persist the current read-URL set to localStorage.
 */
export function writePwaRead(urls: Set<string>): void {
  const store: PwaReadStore = { v: 1, urls: Array.from(urls) };
  window.localStorage.setItem(PWA_READ_LS_KEY, JSON.stringify(store));
}

/**
 * Serialise the current set of read URLs to a JSON string that
 * ``condenseit read-import`` (and ``parse_read_payload``) can consume.
 * Shape: ``{"urls": [...], "exported_at": "...", "source": "condenseit-pwa"}``
 */
export function exportPwaRead(urls: Set<string>): string {
  return JSON.stringify(
    {
      urls: Array.from(urls).sort(),
      exported_at: new Date().toISOString(),
      source: 'condenseit-pwa',
    },
    null,
    2,
  );
}

export function exportPwaRatings(
  store: PwaRatingsStore,
  digestId: number,
): string {
  const ratings = Object.entries(store.byUrl).map(([url, rating]) => ({
    url,
    rating,
  }));
  return JSON.stringify(
    {
      version: 1,
      digest_id: digestId,
      exported_at: new Date().toISOString(),
      source: 'condenseit-pwa',
      ratings,
    },
    null,
    2,
  );
}
