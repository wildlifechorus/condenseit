/**
 * Normalizes a DigestItem produced by an earlier pipeline run where the
 * LLM response was stored verbatim in the `summary` field as a JSON string
 * (e.g. `{ "tldr": "...", "key_takeaways": [...], "summary": "..." }`).
 *
 * If the item already carries structured `tldr` / `key_takeaways` fields, or
 * if `summary` is not parseable JSON, the item is returned unchanged.
 */

import type { DigestItem } from './types';

export function normalizeItem(item: DigestItem): DigestItem {
  /** Already structured — nothing to do. */
  if (item.tldr || (item.key_takeaways && item.key_takeaways.length > 0)) {
    return item;
  }

  const raw = (item.summary ?? '').trim();
  if (!raw.startsWith('{')) return item;

  try {
    const data: unknown = JSON.parse(raw);
    if (typeof data !== 'object' || data === null) return item;

    const d = data as Record<string, unknown>;

    const tldr =
      typeof d['tldr'] === 'string' ? d['tldr'].trim() : '';

    const summary =
      typeof d['summary'] === 'string' ? d['summary'].trim() : '';

    let key_takeaways: string[] = [];
    const kt = d['key_takeaways'];
    if (Array.isArray(kt)) {
      key_takeaways = kt
        .filter((t): t is string => typeof t === 'string' && t.trim() !== '')
        .map((t) => t.trim());
    } else if (typeof kt === 'string') {
      key_takeaways = kt
        .split('\n')
        .map((t) => t.replace(/^[-*]\s+/, '').trim())
        .filter(Boolean);
    }

    if (tldr || summary || key_takeaways.length > 0) {
      return { ...item, tldr, summary: summary || raw, key_takeaways };
    }
  } catch {
    /** Not valid JSON — use as-is. */
  }

  return item;
}
