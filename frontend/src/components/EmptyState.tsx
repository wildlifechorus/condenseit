import type { ComponentChildren } from 'preact';

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ComponentChildren;
  icon?: ComponentChildren;
}

/** Centered empty-state placeholder. */
export function EmptyState({
  title,
  description,
  action,
  icon,
}: EmptyStateProps) {
  return (
    <div class="flex flex-col items-center justify-center py-16 px-6 text-center">
      {icon && (
        <div class="mb-4 text-slate-400 dark:text-slate-600">{icon}</div>
      )}
      <h3 class="text-lg font-semibold text-slate-700 dark:text-slate-300">
        {title}
      </h3>
      {description && (
        <p class="mt-1 text-sm text-slate-500 dark:text-slate-400 max-w-sm">
          {description}
        </p>
      )}
      {action && <div class="mt-4">{action}</div>}
    </div>
  );
}
