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

/** Header "Run digest" button. Used in AppLayout. */
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

  const state = job.value.state;

  return (
    <Button
      size="sm"
      variant={state === 'running' ? 'ghost' : 'primary'}
      disabled={state === 'running'}
      loading={loading.value || state === 'running'}
      onClick={run}
    >
      {state === 'running' ? 'Running…' : 'Run digest'}
    </Button>
  );
}
