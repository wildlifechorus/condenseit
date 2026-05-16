import { useSignal, useComputed } from '@preact/signals';
import { useEffect } from 'preact/hooks';
import { jobSignal } from '../lib/signals';
import { api } from '../lib/api';
import { Button } from './Button';

let pollInterval: ReturnType<typeof setInterval> | null = null;

function startPolling() {
  stopPolling();
  pollInterval = setInterval(async () => {
    try {
      const job = await api.getJobStatus();
      jobSignal.value = job;
      if (job.state !== 'running') stopPolling();
    } catch {
      stopPolling();
    }
  }, 2000);
}

function stopPolling() {
  if (pollInterval !== null) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

/** Header "Run digest" button + progress banner. Used in AppLayout. */
export function JobBanner() {
  const loading = useSignal(false);
  const job = useComputed(() => jobSignal.value);

  useEffect(() => {
    if (job.value.state === 'running') startPolling();
    return stopPolling;
  }, []);

  async function run() {
    loading.value = true;
    try {
      const res = await api.runDigest();
      jobSignal.value = res.job;
      if (res.job.state === 'running') startPolling();
    } catch (err) {
      jobSignal.value = {
        state: 'failed',
        message: err instanceof Error ? err.message : 'Could not start digest.',
      };
    } finally {
      loading.value = false;
    }
  }

  async function dismiss() {
    try {
      const j = await api.dismissJob();
      jobSignal.value = j;
    } catch {
      jobSignal.value = { state: 'idle', message: '' };
    }
  }

  const state = job.value.state;
  const visible = state === 'completed' || state === 'failed';

  const bannerColor =
    state === 'completed'
      ? 'bg-green-50 dark:bg-green-900/20 border-b border-green-200 dark:border-green-800'
      : state === 'failed'
        ? 'bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800'
        : 'bg-teal-50 dark:bg-teal-900/20 border-b border-teal-200 dark:border-teal-800';

  return (
    <>
      <Button
        size="sm"
        variant={state === 'running' ? 'ghost' : 'primary'}
        disabled={state === 'running'}
        loading={loading.value || state === 'running'}
        onClick={run}
      >
        {state === 'running' ? 'Running…' : 'Run digest'}
      </Button>

      {visible && (
        <div
          class={`flex items-start justify-between gap-3 px-4 py-2.5 text-sm ${bannerColor}`}
        >
          <div class="flex-1 min-w-0">
            <span
              class={
                state === 'failed'
                  ? 'text-red-700 dark:text-red-400'
                  : 'text-teal-700 dark:text-teal-300'
              }
            >
              {job.value.message}
            </span>
            {state === 'failed' && job.value.post_display && (
              <pre class="mt-1 text-xs text-slate-500 dark:text-slate-400 whitespace-pre-wrap break-words">
                {job.value.post_display}
              </pre>
            )}
          </div>
          <div class="flex-shrink-0 flex items-center gap-2">
            {(state === 'completed' || state === 'failed') && (
              <Button size="sm" variant="ghost" onClick={dismiss}>
                Dismiss
              </Button>
            )}
            {state === 'completed' && job.value.digest_id && (
              <a
                href={`/?id=${job.value.digest_id}`}
                class="inline-flex items-center px-2.5 py-1.5 text-xs font-semibold bg-teal-600 text-white rounded-md hover:bg-teal-700 transition-colors"
              >
                View digest
              </a>
            )}
          </div>
        </div>
      )}
    </>
  );
}
