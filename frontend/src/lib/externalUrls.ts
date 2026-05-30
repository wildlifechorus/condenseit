/** Stable third-party API URLs for the admin UI. */

export const ITUNES_PODCAST_SEARCH_BASE =
  import.meta.env.VITE_ITUNES_SEARCH_BASE ??
  'https://itunes.apple.com/search';

export function itunesPodcastSearchUrl(query: string): string {
  const params = new URLSearchParams({
    term: query,
    media: 'podcast',
    entity: 'podcast',
    limit: '10',
  });
  return `${ITUNES_PODCAST_SEARCH_BASE}?${params.toString()}`;
}
