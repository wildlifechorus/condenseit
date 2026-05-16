import { useState, useEffect } from 'preact/hooks';
import { api } from '../../lib/api';
import type { AdvisorPageData } from '../../lib/types';
import { Card, CardHeader } from '../../components/Card';
import { StatGrid } from '../../components/StatGrid';
import { Button } from '../../components/Button';
import { Spinner } from '../../components/Spinner';

export function AdvisorPage() {
  const [data, setData] = useState<AdvisorPageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAdvisor()
      .then(setData)
      .catch((e: unknown) => {
        setFlash(e instanceof Error ? e.message : 'Failed to load advisor.');
      })
      .finally(() => setLoading(false));
  }, []);

  async function applyRecommendation() {
    if (!data) return;
    setApplying(true);
    try {
      await api.applyAdvisor(data.recommendation.recommended_model);
      setFlash(`Applied model: ${data.recommendation.recommended_model}`);
      setTimeout(() => setFlash(null), 4000);
    } catch (err) {
      setFlash(err instanceof Error ? err.message : 'Apply failed.');
    } finally {
      setApplying(false);
    }
  }

  if (loading) {
    return (
      <div class="flex items-center justify-center py-20">
        <Spinner size="lg" className="text-teal-600 dark:text-teal-400" />
      </div>
    );
  }

  if (!data) {
    return (
      <p class="text-sm text-red-600 dark:text-red-400 p-4">
        {flash ?? 'Could not load advisor.'}
      </p>
    );
  }

  const { recommendation: rec, weekly, benchmarks } = data;

  return (
    <div class="space-y-5">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
          Model advisor
        </h1>
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Recommends an Ollama model based on your hardware and installed tags.
        </p>
      </div>

      {flash && (
        <div class="px-4 py-3 text-sm rounded-lg bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
          {flash}
        </div>
      )}

      {/* Weekly snapshot */}
      {weekly && (
        <Card>
          <CardHeader
            title="Weekly snapshot"
            description="Stored automatically at most once every 7 days after a digest."
          />
          <p class="text-sm">
            <span class="font-semibold text-slate-900 dark:text-slate-100">
              Recommended:
            </span>{' '}
            <code class="font-mono bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-xs">
              {weekly.recommended_model}
            </code>
          </p>
          <p class="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {weekly.reason}
          </p>
        </Card>
      )}

      {/* Current recommendation */}
      <Card>
        <StatGrid
          stats={[
            { label: 'RAM', value: `${rec.hardware.ram_gb} GB` },
            { label: 'GPU', value: rec.hardware.gpu_hint },
          ]}
        />
        <dl class="space-y-2 text-sm">
          <div>
            <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Current model
            </dt>
            <dd class="mt-0.5 font-mono text-slate-900 dark:text-slate-100">
              {rec.current_model}
            </dd>
          </div>
          <div>
            <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Recommended
            </dt>
            <dd class="mt-0.5 font-mono text-teal-700 dark:text-teal-300 font-semibold">
              {rec.recommended_model}
            </dd>
          </div>
          <div>
            <dt class="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              Reason
            </dt>
            <dd class="mt-0.5 text-slate-600 dark:text-slate-400">{rec.reason}</dd>
          </div>
        </dl>
        <div class="mt-4">
          <Button loading={applying} onClick={applyRecommendation}>
            Apply recommendation
          </Button>
        </div>
      </Card>

      {/* Installed models */}
      <Card>
        <CardHeader title="Installed Ollama models" />
        {rec.installed_models.length > 0 ? (
          <ul class="space-y-1">
            {rec.installed_models.map((m) => (
              <li key={m}>
                <code class="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                  {m}
                </code>
              </li>
            ))}
          </ul>
        ) : (
          <p class="text-sm text-slate-500 dark:text-slate-400">
            No models found. Run{' '}
            <code class="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">
              ollama pull llama3.2:3b
            </code>{' '}
            on the host.
          </p>
        )}
      </Card>

      {/* Benchmark history */}
      {benchmarks.length > 0 && (
        <div class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm overflow-hidden">
          <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
            <h2 class="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Recent benchmarks
            </h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm border-collapse">
              <thead>
                <tr class="bg-slate-50 dark:bg-slate-800/60 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <th class="text-left px-4 py-3">Model</th>
                  <th class="text-left px-4 py-3">Seconds</th>
                  <th class="text-left px-4 py-3">Tok/s</th>
                  <th class="text-left px-4 py-3">When</th>
                </tr>
              </thead>
              <tbody>
                {benchmarks.map((b, i) => (
                  <tr
                    key={i}
                    class="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/30"
                  >
                    <td class="px-4 py-3 font-mono text-xs">{b.model}</td>
                    <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                      {b.elapsed_s}
                    </td>
                    <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                      {b.tokens_per_sec}
                    </td>
                    <td class="px-4 py-3 text-slate-500 dark:text-slate-500">
                      {b.run_at.slice(0, 16).replace('T', ' ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
