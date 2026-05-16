import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { RunLog, RunLogSummary } from '../../lib/types';
import { Card } from '../../components/Card';
import { Spinner } from '../../components/Spinner';

function fmtDate(iso: string): string {
  return iso.slice(0, 16).replace('T', ' ') + ' UTC';
}

export function LogsPage() {
  const [logs, setLogs] = useState<RunLogSummary[]>([]);
  const [selected, setSelected] = useState<RunLog | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingLog, setLoadingLog] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listLogs()
      .then(setLogs)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load logs.');
      })
      .finally(() => setLoading(false));
  }, []);

  async function openLog(id: number) {
    if (selected?.id === id) {
      setSelected(null);
      return;
    }
    setLoadingLog(true);
    try {
      const log = await api.getLog(id);
      setSelected(log);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load log.');
    } finally {
      setLoadingLog(false);
    }
  }

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Run logs
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Full output captured from the most recent digest runs.
        </p>
      </div>

      {error && (
        <div class="px-4 py-3 text-sm rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800">
          {error}
        </div>
      )}

      {logs.length === 0 && !error && (
        <Card>
          <p class="text-sm text-slate-500 dark:text-slate-400 py-2">
            No run logs yet. Logs are saved after each digest run.
          </p>
        </Card>
      )}

      {logs.map((log) => (
        <Card key={log.id} noPad>
          <button
            type="button"
            class="w-full text-left px-5 py-4 flex items-start justify-between gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors rounded-xl"
            onClick={() => openLog(log.id)}
          >
            <div class="min-w-0">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-sm font-semibold text-slate-800 dark:text-slate-200">
                  Run #{log.id}
                </span>
                {log.digest_id != null && (
                  <span class="text-xs text-slate-400 dark:text-slate-500">
                    Digest #{log.digest_id}
                  </span>
                )}
              </div>
              <span class="text-xs text-slate-400 dark:text-slate-500">
                {fmtDate(log.created_at)}
              </span>
            </div>
            <span class="flex-shrink-0 text-xs text-slate-400 dark:text-slate-500 mt-0.5">
              {selected?.id === log.id ? 'Hide' : 'Show'}
            </span>
          </button>

          {selected?.id === log.id && (
            <div class="border-t border-slate-100 dark:border-slate-800 px-5 pb-5 pt-4">
              {loadingLog ? (
                <div class="flex justify-center py-4">
                  <Spinner size="sm" className="text-teal-600 dark:text-teal-400" />
                </div>
              ) : (
                <pre class="text-xs font-mono text-slate-600 dark:text-slate-300 whitespace-pre-wrap break-words overflow-x-auto bg-slate-50 dark:bg-slate-950 rounded-lg p-4 max-h-[60vh] overflow-y-auto">
                  {selected.log_text || '(no log output)'}
                </pre>
              )}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}
