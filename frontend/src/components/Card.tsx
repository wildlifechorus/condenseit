import type { ComponentChildren } from 'preact';

interface CardProps {
  children: ComponentChildren;
  className?: string;
  /** Remove default padding for tables or custom-padded content. */
  noPad?: boolean;
}

/** Standard card container with border and shadow. */
export function Card({ children, className = '', noPad = false }: CardProps) {
  return (
    <div
      class={[
        'bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700',
        'rounded-xl shadow-sm',
        noPad ? '' : 'p-5',
        className,
      ].join(' ')}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  title: string;
  description?: string;
  actions?: ComponentChildren;
}

/** Card header row with title, optional description and action slot. */
export function CardHeader({ title, description, actions }: CardHeaderProps) {
  return (
    <div class="flex items-start justify-between gap-4 mb-4">
      <div>
        <h2 class="text-base font-semibold text-slate-900 dark:text-slate-100">
          {title}
        </h2>
        {description && (
          <p class="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
            {description}
          </p>
        )}
      </div>
      {actions && <div class="flex-shrink-0">{actions}</div>}
    </div>
  );
}
