interface Stat {
  label: string;
  value: string | number;
}

interface StatGridProps {
  stats: Stat[];
}

/** Responsive grid of labelled stat boxes. */
export function StatGrid({ stats }: StatGridProps) {
  return (
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mb-5">
      {stats.map((s) => (
        <div
          key={s.label}
          class="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm"
        >
          <div class="text-xl font-bold text-slate-900 dark:text-slate-100 leading-tight truncate">
            {s.value}
          </div>
          <div class="mt-0.5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {s.label}
          </div>
        </div>
      ))}
    </div>
  );
}
