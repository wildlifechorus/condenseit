import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { AdminOverview } from '../../lib/types';
import { StatGrid } from '../../components/StatGrid';
import { Card, CardHeader } from '../../components/Card';
import { Spinner } from '../../components/Spinner';

export function AdminOverviewPage() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAdminOverview()
      .then(setData)
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : 'Failed to load overview.');
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <p class="text-sm text-red-600 dark:text-red-400 p-4">
        {error ?? 'Unknown error'}
      </p>
    );
  }

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Admin
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Sources, models, and API keys for your digest pipeline.
        </p>
      </div>

      <StatGrid
        stats={[
          { label: 'Sources', value: data.source_count },
          { label: 'LLM provider', value: data.provider },
          { label: 'Model', value: data.model },
        ]}
      />

      <Card>
        <CardHeader title="Quick links" />
        <div class="flex flex-wrap gap-2">
          <a
            href="/admin/sources"
            class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition-colors"
          >
            Manage sources
          </a>
          <a
            href="/admin/llm"
            class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            LLM settings
          </a>
          <a
            href="/admin/advisor"
            class="inline-flex items-center px-4 py-2 text-sm font-semibold bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            Model advisor
          </a>
        </div>
        {data.latest && (
          <p class="mt-4 text-xs text-slate-500 dark:text-slate-400">
            Last digest #{data.latest.id} at{' '}
            {data.latest.created_at.slice(0, 16).replace('T', ' ')} UTC
          </p>
        )}
      </Card>
    </div>
  );
}
