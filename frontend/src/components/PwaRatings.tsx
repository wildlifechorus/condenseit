import { exportPwaRatings, type PwaRatingsStore } from '../lib/pwa-data';
import { Button } from './Button';

interface PwaRatingsToolbarProps {
  /** Live ratings store maintained by the parent. */
  store: PwaRatingsStore;
  digestId: number;
  ratedCount: number;
}

/**
 * Minimal toolbar shown below the digest in PWA mode.
 * Stars are embedded directly in each DigestCard; this component
 * only provides the "Download ratings JSON" action.
 */
export function PwaRatingsToolbar({
  store,
  digestId,
  ratedCount,
}: PwaRatingsToolbarProps) {
  function download() {
    const json = exportPwaRatings(store, digestId);
    const blob = new Blob([json], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'condenseit-ratings.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (ratedCount === 0) return null;

  return (
    <div class="mt-4 flex items-center justify-between gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-3 shadow-sm">
      <p class="text-xs text-slate-500 dark:text-slate-400">
        {ratedCount} item{ratedCount !== 1 ? 's' : ''} rated locally.
        Ratings are imported automatically on the next digest run when{' '}
        <code class="font-mono">CONDENSEIT_RATINGS_IMPORT_URL</code> is
        configured, or download the JSON to import manually.
      </p>
      <Button size='sm' variant='secondary' onClick={download}>
        Download ratings JSON
      </Button>
    </div>
  );
}
